/*
 beebrain field, browser twin of beebrain/brain.py and beebrain/field/.
 the same brain, wiring, senses, paper accounts and forward test, so a bee in the
 browser and a bee in the terminal score a pool the same way. tests/test_field_js.py
 runs this file under node and compares it with python.

 read only data: GET requests to public apis. no keys, no signatures, no orders.
 idea credited to the nerve protocol, github.com/h100envy/nerve
*/
(function (root) {
  "use strict";

  // ------------------------------------------------------------ constants
  const C = {
    FEATS: ["liquidity", "holders", "snipers", "bundle", "creator age", "heat", "accel", "volume"],
    N_BINS: 4, N_KC: 2000, KC_FANIN: 6, KC_ACTIVE: 100, KC_TIE: 0.01, W_INIT: 0.5, MB_GAIN: 2.2,
    MEMORY_LEN: 800, SEEN_OVERLAP: 0.4,
    ANT_NOISE_W: 0.9, ANT_INCONS_W: 0.4, ANT_JITTER: 0.03, OPTIC_HEAT_W: 0.55, OPTIC_ACCEL_W: 0.45,
    OCTOPAMINE_LR: 0.25, PUNISH_LR: 0.25, GHOST_LR: 0.06,
    W_MUSHROOM: 0.5, W_OPTIC: 0.2, W_ANTENNAL: 0.2, W_SNIPERS: 0.1,
    EPS_START: 0.5, EPS_FLOOR: 0.05, EPS_TAU: 15,
    PASS_AT: 0.58, PASS_MIN_ANTENNAL: 0.35, WATCH_AT: 0.47, FLAG_BELOW: 0.5, CONSENSUS_GAIN: 2.5,
    MAX_OPEN: 4, SIZE_PASS: 0.13, SIZE_EXPLORE: 0.04,
    REFLEX_MIN_LIQ: 2000, REFLEX_FDV_LIQ: 250, REFLEX_HONEYPOT_BUYS: 25, REFLEX_DUMP_M5: -50, REFLEX_RUG_H1: -80,
    AGE_FULL_MIN: 4320,
    FEE_SIDE: 0.01, IMPACT_MAX: 0.5, TAKE_PROFIT: 1.0, STOP_LOSS: -0.35, MAX_HOLD_MIN: 30,
    RUG_LIQ_DROP: 0.3, RUG_PRICE: -0.9, START: 500,
    HORIZON_MIN: 15, FWD_FEE: 0.02, DROP_AFTER_MIN: 20, MAX_AGE_DAYS: 30, MAX_FDV: 200e6, FIELD_TTL_MIN: 90,
    RANDOM_MIN_RATE: 0.08, GRADUATE_POOLS: 300, GRADUATE_EDGE: 0.05, FWD_CAP: 5, SEED: 5,
  };
  C.N_INPUTS = C.FEATS.length * C.N_BINS;

  const LIVE_LABELS = {
    liquidity: "liquidity", holders: "buys 1h", snipers: "sell pressure", bundle: "reflex",
    "creator age": "pool age", heat: "heat", accel: "acceleration", volume: "turnover",
  };

  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));

  // --------------------------------------------------------------- rng
  class FieldRng {
    constructor(seed) { this.a = seed >>> 0; }
    random() {
      this.a = (this.a + 0x6D2B79F5) >>> 0;
      const a = this.a;
      let t = Math.imul(a ^ (a >>> 15), 1 | a) >>> 0;
      t = ((t + (Math.imul(t ^ (t >>> 7), 61 | t) >>> 0)) >>> 0) ^ t;
      t >>>= 0;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }
    sample(n, k) {
      const pool = Array.from({ length: n }, (_, i) => i), out = [];
      for (let i = 0; i < k; i++) {
        const j = i + Math.floor(this.random() * (pool.length - i));
        const tmp = pool[i]; pool[i] = pool[j]; pool[j] = tmp;
        out.push(pool[i]);
      }
      return out;
    }
    gauss(mu = 0, sigma = 1) {
      const u1 = 1 - this.random(), u2 = this.random();
      return mu + sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }
  }

  // -------------------------------------------------------------- brain
  class BeeBrain {
    constructor(rng) {
      this.rng = rng;
      this.kcIn = [];
      for (let k = 0; k < C.N_KC; k++) this.kcIn.push(rng.sample(C.N_INPUTS, C.KC_FANIN));
      this.tie = [];
      for (let k = 0; k < C.N_KC; k++) this.tie.push(rng.random() * C.KC_TIE);
      this.w = new Array(C.N_KC).fill(C.W_INIT);
      this.memory = [];
      this.eps = C.EPS_START;
      this.resolved = 0;
      this.sugar = 0;
      this.pain = 0;
    }
    code(obs) {
      const on = new Set();
      C.FEATS.forEach((f, i) => on.add(i * C.N_BINS + Math.min(C.N_BINS - 1, Math.floor(obs[f] * C.N_BINS))));
      const score = this.kcIn.map((ins, k) => [ins.reduce((n, j) => n + (on.has(j) ? 1 : 0), 0) + this.tie[k], k]);
      score.sort((x, y) => (y[0] - x[0]) || (y[1] - x[1]));
      return score.slice(0, C.KC_ACTIVE).map((x) => x[1]).sort((a, b) => a - b);
    }
    value(act) { let s = 0; for (const k of act) s += this.w[k]; return s / C.KC_ACTIVE; }
    think(pool) {
      const o = pool.obs;
      const incons = Math.abs(o.volume - o.liquidity) * 0.5 + Math.abs(o.holders - (1 - o.snipers)) * 0.5;
      const antennal = clamp(1.0 - C.ANT_NOISE_W * pool.noise - C.ANT_INCONS_W * incons + this.rng.gauss(0, C.ANT_JITTER));
      const optic = clamp(C.OPTIC_HEAT_W * o.heat + C.OPTIC_ACCEL_W * o.accel);
      const act = this.code(o);
      const mbVal = this.value(act);
      const actSet = new Set(act);
      let seen = 0, won = 0;
      for (const [s, w] of this.memory) {
        let n = 0; for (const k of s) if (actSet.has(k)) n++;
        if (n >= C.KC_ACTIVE * C.SEEN_OVERLAP) { seen++; won += w; }
      }
      const mushroom = clamp(0.5 + (mbVal - 0.5) * C.MB_GAIN);
      const comb = C.W_MUSHROOM * mushroom + C.W_OPTIC * optic + C.W_ANTENNAL * antennal + C.W_SNIPERS * (1 - o.snipers);
      const explore = this.rng.random() < this.eps;
      let verdict;
      if (o.bundle > 0.5) verdict = "SKIP";
      else if (comb >= C.PASS_AT && antennal >= C.PASS_MIN_ANTENNAL) verdict = "PASS";
      else if (comb >= C.WATCH_AT) verdict = "WATCH";
      else verdict = "SKIP";
      const flag = verdict === "PASS" && antennal < C.FLAG_BELOW;
      const take = verdict === "PASS" || (verdict === "WATCH" && explore);
      const lobes = { mushroom, antennal, optic, central: comb };
      const vals = [mushroom, antennal, optic, comb];
      const m = vals.reduce((a, b) => a + b, 0) / 4;
      const consensus = 1 - Math.sqrt(vals.reduce((a, v) => a + (v - m) ** 2, 0) / 4) * C.CONSENSUS_GAIN;
      return { act, lobes, seen, won, verdict, flag, explore: explore && verdict === "WATCH", take, consensus: clamp(consensus), comb };
    }
    octopamine(act, lr = C.OCTOPAMINE_LR) { this.sugar++; for (const k of act) this.w[k] += lr * (1.0 - this.w[k]); }
    punish(act, lr = C.PUNISH_LR) { this.pain++; for (const k of act) this.w[k] += lr * (0.0 - this.w[k]); }
    learn(act, won, lr) { if (won) this.octopamine(act, lr); else this.punish(act, lr); }
    remember(act, won) {
      this.memory.push([act, won ? 1 : 0]);
      if (this.memory.length > C.MEMORY_LEN) this.memory.shift();
    }
    afterTrade(act, won) {
      this.learn(act, won, won ? C.OCTOPAMINE_LR : C.PUNISH_LR);
      this.remember(act, won);
      this.resolved++;
      this.eps = Math.max(C.EPS_FLOOR, C.EPS_START * Math.exp(-this.resolved / C.EPS_TAU));
    }
  }

  function waggleVector(pool, t) {
    const r2 = (x) => Math.round(x * 100) / 100, L = t.lobes;
    return {
      pool: pool.name,
      mushroom: { value: r2(L.mushroom), seen: t.seen, printed: t.won },
      antennal: { value: r2(L.antennal), noise: r2(pool.noise) },
      optic: { value: r2(L.optic), heat: r2(pool.obs.heat), accel: r2(pool.obs.accel) },
      central: { value: r2(L.central), mode: t.explore ? "explore" : "exploit" },
      motor: { verdict: t.verdict, flag: t.flag },
      consensus: r2(t.consensus),
      kenyon_active: t.act.length,
    };
  }

  // ------------------------------------------------------------- senses
  const num = (v, d = 0) => { const f = Number(v); return v === null || v === undefined || v === "" || !isFinite(f) ? d : f; };
  const g = (o, ...ks) => ks.reduce((x, k) => (x && typeof x === "object" ? x[k] : undefined), o);

  function normDexscreener(p) {
    return {
      chain: p.chainId || "", pair: p.pairAddress || "", token: g(p, "baseToken", "address") || "",
      symbol: String(g(p, "baseToken", "symbol") || "?").slice(0, 12), name: String(g(p, "baseToken", "name") || "").slice(0, 40),
      dex: p.dexId || "", url: p.url || "", price: num(p.priceUsd), liq: num(g(p, "liquidity", "usd")), fdv: num(p.fdv),
      created_ms: num(p.pairCreatedAt),
      buys_m5: num(g(p, "txns", "m5", "buys")), sells_m5: num(g(p, "txns", "m5", "sells")),
      buys_h1: num(g(p, "txns", "h1", "buys")), sells_h1: num(g(p, "txns", "h1", "sells")),
      vol_m5: num(g(p, "volume", "m5")), vol_h1: num(g(p, "volume", "h1")),
      chg_m5: num(g(p, "priceChange", "m5")), chg_h1: num(g(p, "priceChange", "h1")), src: "dexscreener",
    };
  }

  function normGecko(p, chain, tokens) {
    const a = p.attributes || {}, name = a.name || "";
    const bid = g(p, "relationships", "base_token", "data", "id") || "";
    const tok = (tokens || {})[bid] || {};
    const addr = a.address || "";
    const ms = Date.parse((a.pool_created_at || "").slice(0, 19) + "Z");
    return {
      chain, pair: addr, token: tok.address || bid.split("_").slice(1).join("_"),
      symbol: String(tok.symbol || name.split(" / ")[0] || "?").slice(0, 12), name: String(tok.name || name).slice(0, 40),
      dex: g(p, "relationships", "dex", "data", "id") || "", url: "https://dexscreener.com/" + chain + "/" + addr.toLowerCase(),
      price: num(a.base_token_price_usd), liq: num(a.reserve_in_usd), fdv: num(a.fdv_usd), created_ms: isFinite(ms) ? ms : 0,
      buys_m5: num(g(a, "transactions", "m5", "buys")), sells_m5: num(g(a, "transactions", "m5", "sells")),
      buys_h1: num(g(a, "transactions", "h1", "buys")), sells_h1: num(g(a, "transactions", "h1", "sells")),
      vol_m5: num(g(a, "volume_usd", "m5")), vol_h1: num(g(a, "volume_usd", "h1")),
      chg_m5: num(g(a, "price_change_percentage", "m5")), chg_h1: num(g(a, "price_change_percentage", "h1")), src: "geckoterminal",
    };
  }

  function reflex(s) {
    const out = [];
    if (s.liq <= 0) out.push("no pool liquidity yet, bonding curve");
    else if (s.liq < C.REFLEX_MIN_LIQ) out.push("thin liquidity");
    if (s.liq > 0 && s.fdv / s.liq > C.REFLEX_FDV_LIQ) out.push("fdv far above liquidity");
    if (s.buys_h1 >= C.REFLEX_HONEYPOT_BUYS && s.sells_h1 === 0) out.push("no sells, possible honeypot");
    if (s.chg_m5 <= C.REFLEX_DUMP_M5) out.push("dumping now");
    if (s.chg_h1 <= C.REFLEX_RUG_H1) out.push("rugged in the last hour");
    return out;
  }

  function heatRank(v, vols) {
    if (!vols.length) return 0.5;
    let below = 0, same = 0;
    for (const x of vols) { if (x < v) below++; else if (x === v) same++; }
    return clamp((below + 0.5 * same) / vols.length);
  }

  function features(s, vols, nowMs) {
    const liq = Math.max(s.liq, 1);
    const ageMin = s.created_ms ? Math.max(0, (nowMs - s.created_ms) / 60000) : 0;
    const m5 = s.buys_m5 + s.sells_m5;
    const pace = s.vol_m5 * 12 / Math.max(s.vol_h1, 1);
    const reasons = reflex(s);
    const obs = {
      liquidity: clamp((Math.log10(liq) - 3) / 3),
      holders: clamp(Math.log10(1 + s.buys_h1) / 3.3),
      snipers: m5 >= 4 ? s.sells_m5 / m5 : 0.5,
      bundle: reasons.length ? 1 : 0,
      "creator age": clamp(Math.log10(1 + ageMin) / Math.log10(1 + C.AGE_FULL_MIN)),
      heat: heatRank(s.vol_h1, vols),
      accel: clamp(0.5 * clamp(pace / 2) + 0.5 * clamp(0.5 + s.chg_m5 / 40)),
      volume: clamp(Math.log10(1 + 10 * s.vol_h1 / liq) / 2),
    };
    const tx = s.buys_h1 + s.sells_h1;
    const noise = clamp(1 - Math.log10(1 + tx) / 3);
    return { obs, noise, reasons };
  }

  // -------------------------------------------------------------- paper
  const impact = (size, liq) => (liq <= 0 ? C.IMPACT_MAX : Math.min(C.IMPACT_MAX, 2 * size / liq));

  class Position {
    constructor(id, s, size, t, act, why) {
      Object.assign(this, {
        id, pair: s.pair, symbol: s.symbol, url: s.url || "", size, t0: t, p0: s.price, liq0: s.liq,
        fill: s.price * (1 + impact(size, s.liq)), price: s.price, liq: s.liq, act: act ? act.slice() : [], why: why || "", peak: 0, low: 0,
      });
      this.qty = this.fill > 0 ? size * (1 - C.FEE_SIDE) / this.fill : 0;
    }
    value() { const gross = this.qty * this.price; return gross * (1 - impact(gross, this.liq)) * (1 - C.FEE_SIDE); }
    ret() { return this.size ? this.value() / this.size - 1 : 0; }
    static from(d) { return Object.assign(Object.create(Position.prototype), d); }
  }

  class Account {
    constructor(name, start = C.START) {
      Object.assign(this, { name, start, cash: start, open: [], closed: [], peak: start, max_dd: 0, seq: 0, hist: [[0, start]] });
    }
    get equity() { return this.cash + this.open.reduce((a, p) => a + p.value(), 0); }
    buy(s, size, t, act, why) {
      size = Math.min(size, this.cash);
      if (size < 1 || !(s.price > 0)) return null;
      this.seq++;
      const pos = new Position(this.name + "-" + this.seq, s, size, t, act, why);
      this.cash -= size;
      this.open.push(pos);
      return pos;
    }
    close(pos, t, reason) {
      const out = pos.value();
      this.cash += out;
      this.open = this.open.filter((p) => p !== pos);
      const rec = { id: pos.id, pair: pos.pair, symbol: pos.symbol, size: pos.size, out, pnl: out - pos.size,
        ret: pos.size ? out / pos.size - 1 : 0, t0: pos.t0, t1: t, reason, act: pos.act, url: pos.url };
      this.closed.push(rec);
      if (this.closed.length > 500) this.closed.shift();
      return rec;
    }
    mark(field, t, exits = true) {
      const done = [];
      for (const pos of this.open.slice()) {
        const s = field.get(pos.pair);
        if (s && s.price > 0) { pos.price = s.price; pos.liq = s.liq; }
        const r = pos.ret();
        pos.peak = Math.max(pos.peak, r); pos.low = Math.min(pos.low, r);
        if (!exits) continue;
        const held = (t - pos.t0) / 60000, move = pos.p0 ? pos.price / pos.p0 - 1 : 0;
        if ((pos.liq0 && pos.liq < pos.liq0 * C.RUG_LIQ_DROP) || move <= C.RUG_PRICE) done.push(this.close(pos, t, "rug"));
        else if (r >= C.TAKE_PROFIT) done.push(this.close(pos, t, "take profit"));
        else if (r <= C.STOP_LOSS) done.push(this.close(pos, t, "stop loss"));
        else if (held >= C.MAX_HOLD_MIN) done.push(this.close(pos, t, "max hold"));
      }
      const e = this.equity;
      this.peak = Math.max(this.peak, e);
      this.max_dd = Math.min(this.max_dd, this.peak ? e / this.peak - 1 : 0);
      return done;
    }
    stats() {
      const n = this.closed.length, wins = this.closed.filter((c) => c.pnl > 0).length;
      return { name: this.name, equity: this.equity, start: this.start, trades: n, wins, win_rate: n ? wins / n : 0,
        open: this.open.length, max_drawdown: this.max_dd };
    }
    toJSON() { return { name: this.name, start: this.start, cash: this.cash, open: this.open, closed: this.closed,
      peak: this.peak, max_dd: this.max_dd, seq: this.seq, hist: this.hist.slice(-400) }; }
    static from(d) { const a = new Account(d.name, d.start); Object.assign(a, d); a.open = d.open.map(Position.from); return a; }
  }

  // ------------------------------------------------------------ session
  class FieldSession {
    constructor(chain = "solana", seed = C.SEED, horizonMin = C.HORIZON_MIN) {
      this.chain = chain; this.seed = seed; this.horizonMin = horizonMin;
      this.rng = new FieldRng(seed);
      this.brain = new BeeBrain(this.rng);
      this.rrand = new FieldRng(seed * 7 + 99);
      this.accounts = { you: new Account("you"), bee: new Account("bee"), random: new Account("random") };
      this.field = new Map(); this.seen = new Set(); this.queue = []; this.recent = []; this.shadows = [];
      this.fwd = { PASS: { n: 0, wins: 0, net: 0 }, WATCH: { n: 0, wins: 0, net: 0 }, SKIP: { n: 0, wins: 0, net: 0 }, BRAIN_SKIP: { n: 0, wins: 0, net: 0 } };
      this.fwdRecent = []; this.fwdDropped = 0;
      this.counts = { PASS: 0, WATCH: 0, SKIP: 0 };
      this.scored = 0; this.beeTakes = 0; this.reflexed = 0;
      this.log = []; this.last = null; this.started = Date.now();
    }
    say(t, msg, tone = "dim") { this.log.push([t, msg, tone]); if (this.log.length > 80) this.log.shift(); }
    eligible(s, now) {
      if (s.chain !== this.chain || !(s.price > 0) || !s.pair) return false;
      if (s.created_ms && (now - s.created_ms) / 86400000 > C.MAX_AGE_DAYS) return false;
      return (s.fdv || 0) <= C.MAX_FDV;
    }
    ingest(snaps, now) {
      let added = 0;
      for (const s0 of snaps) {
        const s = Object.assign({ t_ms: now }, s0);
        if (this.field.has(s.pair) || this.eligible(s, now)) this.field.set(s.pair, s);
        if (s.pair && !this.seen.has(s.pair) && this.eligible(s, now)) { this.seen.add(s.pair); this.queue.push(s.pair); added++; }
      }
      const keep = new Set(this.tracked(1e6)), cutoff = now - C.FIELD_TTL_MIN * 60000, q = new Set(this.queue);
      for (const [p, s] of this.field) if (s.t_ms < cutoff && !keep.has(p) && !q.has(p)) this.field.delete(p);
      return added;
    }
    tracked(limit = 30) {
      const out = [];
      for (const a of Object.values(this.accounts)) for (const p of a.open) if (!out.includes(p.pair)) out.push(p.pair);
      for (const sh of this.shadows.slice().sort((x, y) => x.due - y.due)) if (!out.includes(sh.pair)) out.push(sh.pair);
      return out.slice(0, limit);
    }
    scoreNext(now) {
      while (this.queue.length) { const s = this.field.get(this.queue.shift()); if (s) return this.score(s, now); }
      return null;
    }
    score(s, now) {
      const vols = Array.from(this.field.values(), (x) => x.vol_h1);
      const { obs, noise, reasons } = features(s, vols, now);
      this.scored++;
      const pool = { name: "$" + s.symbol.toUpperCase(), obs, noise };
      const t = this.brain.think(pool);
      const v = t.verdict;
      this.counts[v]++;
      if (reasons.length) this.reflexed++;
      const rec = { n: this.scored, t: now, pair: s.pair, symbol: s.symbol, name: s.name, url: s.url, price: s.price, liq: s.liq,
        obs, noise, reasons, verdict: v, comb: t.comb, take: t.take, explore: t.explore, flag: t.flag,
        vector: waggleVector(pool, t), act: t.act, lobes: t.lobes, took: false };
      const bee = this.accounts.bee;
      if (t.take && bee.open.length < C.MAX_OPEN) {
        const size = bee.equity * (t.explore ? C.SIZE_EXPLORE : C.SIZE_PASS);
        if (bee.buy(s, size, now, t.act, t.explore ? "explore" : "pass")) {
          rec.took = true; this.beeTakes++;
          this.say(now, "bee " + (t.explore ? "explores " : "enters ") + pool.name + " $" + size.toFixed(0) + "  mb " + t.lobes.mushroom.toFixed(2), "entry");
        }
      }
      const rand = this.accounts.random, rate = Math.max(C.RANDOM_MIN_RATE, this.beeTakes / this.scored);
      if (!reasons.length && this.rrand.random() < rate && rand.open.length < C.MAX_OPEN) rand.buy(s, rand.equity * C.SIZE_PASS, now, null, "random");
      if (reasons.length && this.rrand.random() < 0.3) this.say(now, pool.name + " reflex: " + reasons[0], "dim");
      this.shadows.push({ pair: s.pair, symbol: s.symbol, t0: now, p0: s.price, due: now + this.horizonMin * 60000, verdict: v, act: t.act, took: rec.took, reasons });
      this.recent.push(rec); if (this.recent.length > 60) this.recent.shift();
      this.last = rec;
      return rec;
    }
    mark(now) {
      const closed = [];
      for (const [name, a] of Object.entries(this.accounts)) {
        for (const c of a.mark(this.field, now)) {
          const won = c.pnl > 0;
          closed.push([name, c]);
          if (name === "bee") {
            this.brain.afterTrade(c.act, won);
            this.say(now, "bee closed $" + c.symbol + " " + pct(c.ret) + ", " + c.reason + ". " + (won ? "sugar" : "punishment"), won ? "good" : "bad");
          } else if (name === "you") this.say(now, "you closed $" + c.symbol + " " + pct(c.ret) + ", " + c.reason, won ? "good" : "bad");
        }
        const last = a.hist[a.hist.length - 1];
        if (!last || now - last[0] > 60000) { a.hist.push([now, a.equity]); if (a.hist.length > 600) a.hist.shift(); }
      }
      const keep = [];
      for (const sh of this.shadows) {
        const s = this.field.get(sh.pair);
        if (now < sh.due) keep.push(sh);
        else if (s && s.t_ms >= sh.due && s.price > 0 && sh.p0 > 0) this.resolve(sh, s.price);
        else if (now - sh.due > C.DROP_AFTER_MIN * 60000) this.fwdDropped++;
        else keep.push(sh);
      }
      this.shadows = keep;
      return closed;
    }
    resolve(sh, price) {
      const net = (1 + (price / sh.p0 - 1)) * (1 - C.FWD_FEE) - 1, won = net > 0;
      const keys = [sh.verdict].concat(sh.verdict === "SKIP" && !(sh.reasons && sh.reasons.length) ? ["BRAIN_SKIP"] : []);
      for (const key of keys) {
        const f = this.fwd[key] || (this.fwd[key] = { n: 0, wins: 0, net: 0 });
        f.n++; f.wins += won ? 1 : 0; f.net += Math.min(net, C.FWD_CAP);
      }
      this.fwdRecent.push([sh.symbol, sh.verdict, net]); if (this.fwdRecent.length > 200) this.fwdRecent.shift();
      if (!sh.took) { this.brain.learn(sh.act, won, C.GHOST_LR); this.brain.remember(sh.act, won); }
    }
    buy(pair, usd, now) {
      const s = this.field.get(pair); if (!s) return null;
      const pos = this.accounts.you.buy(s, usd, now, null, "manual");
      if (pos) this.say(now, "you bought $" + s.symbol + " $" + pos.size.toFixed(0), "entry");
      return pos;
    }
    sell(id, now) {
      const you = this.accounts.you, p = you.open.find((x) => x.id === id); if (!p) return null;
      const c = you.close(p, now, "manual");
      this.say(now, "you sold $" + c.symbol + " " + pct(c.ret), c.pnl > 0 ? "good" : "bad");
      return c;
    }
    forward() {
      const out = {};
      for (const [v, f] of Object.entries(this.fwd)) out[v] = { n: f.n, hit: f.n ? f.wins / f.n : 0, avg_net: f.n ? f.net / f.n : 0 };
      return out;
    }
    gate() {
      const fw = this.forward(), n = fw.PASS.n + fw.WATCH.n + fw.SKIP.n;
      const edge = fw.PASS.n && fw.BRAIN_SKIP.n ? fw.PASS.avg_net - fw.BRAIN_SKIP.avg_net : 0;
      const bee = this.accounts.bee.equity, rnd = this.accounts.random.equity;
      const checks = [
        ["forward tested pools", n >= C.GRADUATE_POOLS, n + " of " + C.GRADUATE_POOLS],
        ["PASS beats brain SKIP", edge >= C.GRADUATE_EDGE, pct(edge, 1) + " of +" + (C.GRADUATE_EDGE * 100).toFixed(0) + "%"],
        ["bee beats random", bee > rnd, "$" + bee.toFixed(0) + " vs $" + rnd.toFixed(0)],
      ];
      return { open: checks.every((c) => c[1]), checks };
    }
    toJSON() {
      const b = this.brain;
      return { v: 1, chain: this.chain, seed: this.seed, horizonMin: this.horizonMin, rng: this.rng.a, rrand: this.rrand.a,
        brain: { w: b.w, eps: b.eps, resolved: b.resolved, sugar: b.sugar, pain: b.pain, memory: b.memory.slice(-300) },
        accounts: this.accounts, shadows: this.shadows, fwd: this.fwd, fwdDropped: this.fwdDropped, fwdRecent: this.fwdRecent.slice(-60),
        counts: this.counts, scored: this.scored, beeTakes: this.beeTakes, reflexed: this.reflexed,
        seen: Array.from(this.seen).slice(-3000), log: this.log.slice(-40), started: this.started };
    }
    static from(d) {
      const s = new FieldSession(d.chain, d.seed, d.horizonMin);
      s.rng.a = d.rng >>> 0; s.rrand.a = d.rrand >>> 0;
      Object.assign(s.brain, { w: d.brain.w, eps: d.brain.eps, resolved: d.brain.resolved, sugar: d.brain.sugar, pain: d.brain.pain, memory: d.brain.memory });
      s.accounts = { you: Account.from(d.accounts.you), bee: Account.from(d.accounts.bee), random: Account.from(d.accounts.random) };
      d.fwd.BRAIN_SKIP = d.fwd.BRAIN_SKIP || { n: 0, wins: 0, net: 0 };
      Object.assign(s, { shadows: d.shadows, fwd: d.fwd, fwdDropped: d.fwdDropped, fwdRecent: d.fwdRecent || [], counts: d.counts,
        scored: d.scored, beeTakes: d.beeTakes, reflexed: d.reflexed, seen: new Set(d.seen), log: d.log || [], started: d.started || Date.now() });
      return s;
    }
  }

  function pct(x, digits = 0) { return (x >= 0 ? "+" : "") + (x * 100).toFixed(digits) + "%"; }

  // --------------------------------------------------------------- feed
  const DS = "https://api.dexscreener.com", GT = "https://api.geckoterminal.com/api/v2";
  const GT_NETWORK = { solana: "solana", base: "base", bsc: "bsc" };

  class Feed {
    constructor(chain, fetchJson) {
      this.chain = chain;
      this.fetchJson = fetchJson || (async (u) => {
        const r = await fetch(u, { headers: { Accept: "application/json" } });
        if (r.status === 429) { const e = new Error("rate limited"); e.rate = true; throw e; }
        if (!r.ok) throw new Error("http " + r.status);
        return r.json();
      });
      this.next = { ds: 0, gt: 0, px: 0 }; this.gtWait = 90; this.gtTurn = 0; this.calls = 0; this.errors = 0; this.status = "starting";
    }
    async get(u) { this.calls++; return this.fetchJson(u); }
    async discoverDs() {
      const tokens = [];
      for (const path of ["/token-profiles/latest/v1", "/token-boosts/latest/v1", "/token-boosts/top/v1"]) {
        const list = await this.get(DS + path);
        for (const t of list || []) if (t.chainId === this.chain && !tokens.includes(t.tokenAddress)) tokens.push(t.tokenAddress);
      }
      const best = new Map();
      for (let i = 0; i < tokens.length; i += 30) {
        const pairs = await this.get(DS + "/tokens/v1/" + this.chain + "/" + tokens.slice(i, i + 30).join(","));
        for (const p of pairs || []) { const s = normDexscreener(p); const cur = best.get(s.token); if (!cur || s.liq > cur.liq) best.set(s.token, s); }
      }
      return Array.from(best.values());
    }
    async discoverGt() {
      const kind = this.gtTurn++ % 2 === 0 ? "new_pools?page=1&" : "trending_pools?duration=5m&";
      const d = await this.get(GT + "/networks/" + GT_NETWORK[this.chain] + "/" + kind + "include=base_token");
      const toks = {}; for (const t of d.included || []) toks[t.id] = t.attributes || {};
      return (d.data || []).map((p) => normGecko(p, this.chain, toks));
    }
    async refresh(pairs) {
      const out = [];
      for (let i = 0; i < pairs.length; i += 30) {
        const d = await this.get(DS + "/latest/dex/pairs/" + this.chain + "/" + pairs.slice(i, i + 30).join(","));
        for (const p of (d && d.pairs) || []) out.push(normDexscreener(p));
      }
      return out;
    }
    async poll(nowS, tracked) {
      let fresh = [], found = [];
      try {
        if (nowS >= this.next.ds) { this.next.ds = nowS + 30; found = found.concat(await this.discoverDs()); }
        if (GT_NETWORK[this.chain] && nowS >= this.next.gt) {
          try { found = found.concat(await this.discoverGt()); this.gtWait = 90; }
          catch (e) { if (e.rate) this.gtWait = Math.min(600, this.gtWait * 2); else throw e; }
          this.next.gt = nowS + this.gtWait;
        }
        if (tracked.length && nowS >= this.next.px) { this.next.px = nowS + 15; fresh = await this.refresh(tracked); }
        this.status = "live";
      } catch (e) { this.errors++; this.status = "feed error, retrying"; }
      return { found, fresh };
    }
  }

  const api = { C, LIVE_LABELS, clamp, FieldRng, BeeBrain, waggleVector, normDexscreener, normGecko, reflex, heatRank, features,
    impact, Position, Account, FieldSession, Feed, pct };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.Bee = api;
})(typeof self !== "undefined" ? self : this);
