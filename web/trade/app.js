/*
 beebrain field, the page. the bee scores real pools, three paper accounts race.
 all text from the apis goes in through textContent, never as html.
 idea credited to the nerve protocol, github.com/h100envy/nerve
*/
(function () {
  "use strict";
  const B = window.Bee, C = B.C;
  const CHAINS = ["solana", "base", "bsc", "robinhood"];
  const KEY = (c) => "beebrain.field.v1." + c;
  const $ = (id) => document.getElementById(id);
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------- helpers
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  const usd = (v) => (v <= 0 ? "curve" : v >= 1e6 ? "$" + (v / 1e6).toFixed(1) + "m" : v >= 1e3 ? "$" + (v / 1e3).toFixed(0) + "k" : "$" + v.toFixed(0));
  const money = (v) => "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  const age = (now, ms) => {
    if (!ms) return "?";
    const m = (now - ms) / 60000;
    return m < 90 ? Math.floor(m) + "m" : m < 2880 ? Math.round(m / 60) + "h" : Math.round(m / 1440) + "d";
  };
  const safeUrl = (u) => (/^https:\/\/dexscreener\.com\//.test(u || "") ? u : null);
  const vclass = (v) => "v-" + v.toLowerCase();
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode, keep going in memory */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
  };

  // --------------------------------------------------------------- state
  let chain = store.get("beebrain.field.chain");
  if (!CHAINS.includes(chain)) chain = "solana";
  let S, feed, selected = null, follow = true, polling = false, resetArmed = 0;
  const trails = new Map();          // pair -> [[t, price]], this visit only
  function note(snaps, now) {
    for (const s of snaps) {
      if (!(s.price > 0)) continue;
      const tr = trails.get(s.pair) || [];
      if (!tr.length || now - tr[tr.length - 1][0] > 4000) tr.push([now, s.price]);
      if (tr.length > 400) tr.shift();
      trails.set(s.pair, tr);
    }
  }
  const T = { score: 0, mark: 0, poll: 0, save: 0, ui: 0 };

  function load(c) {
    const raw = store.get(KEY(c));
    if (raw) { try { return B.FieldSession.from(JSON.parse(raw)); } catch (e) { /* start clean */ } }
    const s = new B.FieldSession(c);
    // a new visitor gets the bee a long headless run trained on this chain, if there is one
    fetch("seed-" + c + ".json").then((r) => (r.ok ? r.json() : null)).then((seed) => {
      if (seed && S === s && S.scored === 0 && s.seedWith(seed.memory, seed.label)) { save(); renderSeeded(); }
    }).catch(() => {});
    return s;
  }
  function renderSeeded() {
    const p = $("seeded");
    p.hidden = !S.seededFrom;
    p.textContent = S.seededFrom ? "this bee arrived with memory: " + S.seededFrom + ". it keeps learning here." : "";
  }
  function save() { if (S) store.set(KEY(S.chain), JSON.stringify(S)); }
  function start(c) {
    if (S) save();
    chain = c; store.set("beebrain.field.chain", c);
    S = load(c); feed = new B.Feed(c); selected = null; follow = true;
    T.poll = 0;
    for (const b of document.querySelectorAll("[data-chain]")) b.setAttribute("aria-pressed", String(b.dataset.chain === c));
    renderSeeded();
    renderAll();
  }

  // ---------------------------------------------------------------- loop
  async function poll() {
    if (polling) return;
    polling = true;
    try {
      const track = S.tracked(29);
      if (selected && !track.includes(selected.pair)) track.push(selected.pair);
      const { found, fresh } = await feed.poll(Date.now() / 1000, track);
      const now = Date.now();
      S.ingest(found, now); S.ingest(fresh, now); note(fresh, now); note(found, now);
    } finally { polling = false; }
  }

  function tick() {
    const now = Date.now();
    if (now - T.poll > 3000) { T.poll = now; poll(); }
    if (now - T.mark > 3000) { T.mark = now; S.mark(now); }
    const every = S.queue.length > 40 ? 900 : S.queue.length > 12 ? 1600 : 2400;
    if (now - T.score > every && S.queue.length) {
      T.score = now;
      const r = S.scoreNext(now);
      if (r) { if (follow) selected = r; brain.fire(r); if (r.verdict === "PASS") notifyPass(r); }
    }
    if (now - T.save > 10000) { T.save = now; save(); }
    if (now - T.ui > 500) { T.ui = now; renderAll(); }
  }

  // -------------------------------------------------------------- render
  let signalsSeen = 0;
  function renderSignals() {
    const ul = $("signals");
    ul.replaceChildren();
    const passes = S.recent.filter((r) => r.verdict === "PASS").slice(-12).reverse();
    if (!passes.length) { ul.append(el("li", "empty", "no pass yet. most pools are skipped, that is the job.")); return; }
    for (const r of passes) {
      const li = el("li");
      const go = el("button", "mini", "focus");
      go.type = "button"; go.setAttribute("aria-label", "focus $" + r.symbol);
      go.addEventListener("click", () => { selected = r; follow = false; renderAll(); brain.fire(r); });
      const cp = el("button", "mini", "CA");
      cp.type = "button"; cp.setAttribute("aria-label", "copy contract address of $" + r.symbol);
      cp.addEventListener("click", () => copyCa(r.token, cp));
      li.append(el("span", "sym", "$" + r.symbol), el("span", "dim", new Date(r.t).toTimeString().slice(0, 5)), go, cp);
      ul.append(li);
    }
  }
  function notifyPass(r) {
    if (!notifyOn || !("Notification" in window) || Notification.permission !== "granted") return;
    try { new Notification("the bee passed $" + r.symbol, { body: "score " + r.comb.toFixed(2) + " · liq " + usd(r.liq) + " · paper only, not advice", tag: r.pair }); }
    catch (e) { /* some browsers only allow notifications from a service worker */ }
  }
  let notifyOn = store.get("beebrain.field.notify") === "1";
  async function copyCa(ca, btn) {
    if (!ca) return;
    try { await navigator.clipboard.writeText(ca); btn.textContent = "copied"; }
    catch (e) { btn.textContent = ca.slice(0, 6) + "…"; }
    setTimeout(() => { btn.textContent = btn.id === "copy-ca" ? "copy CA" : "CA"; }, 1500);
  }

  function renderAll() {
    renderSignals();
    renderStatus(); renderField(); renderFocus(); renderTrail(); renderRace(); renderForward(); renderLog();
  }

  function renderTrail() {
    const svg = $("trail"), mv = $("trail-move");
    svg.replaceChildren(); mv.textContent = "";
    const r = selected; if (!r) return;
    const pts = [[r.t, r.price]].concat((trails.get(r.pair) || []).filter((p) => p[0] > r.t));
    const due = r.t + C.HORIZON_MIN * 60000, tEnd = Math.max(due, pts[pts.length - 1][0]);
    const ys = pts.map((p) => p[1]).concat([r.price]), lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || hi * 0.01 || 1;
    const X = (t) => ((t - r.t) / (tEnd - r.t)) * 400, Y = (p) => 64 - ((p - lo) / span) * 58;
    const ns = "http://www.w3.org/2000/svg", mk = (tag, cls, attrs) => {
      const e = document.createElementNS(ns, tag); e.setAttribute("class", cls);
      for (const k in attrs) e.setAttribute(k, attrs[k]); svg.append(e); return e; };
    mk("line", "base", { x1: 0, x2: 400, y1: Y(r.price), y2: Y(r.price) });
    mk("line", "due", { x1: X(due), x2: X(due), y1: 0, y2: 70 });
    if (pts.length > 1) mk("path", "line", { d: pts.map((p, i) => (i ? "L" : "M") + X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1)).join(" ") });
    const last = pts[pts.length - 1][1], m = last / r.price - 1, mins = (pts[pts.length - 1][0] - r.t) / 60000;
    mv.textContent = pts.length > 1 ? B.pct(m, 1) + " in " + mins.toFixed(0) + " min" + (mins >= C.HORIZON_MIN ? " · verdict checked" : "") : "watching";
    mv.className = "num " + (m >= 0 ? "up" : "down");
  }

  function renderStatus() {
    const st = feed ? feed.status : "starting";
    $("status-text").textContent = st === "live" ? "live · " + S.field.size + " pools in view" : st;
    $("status").className = "status " + (st === "live" ? "ok" : st === "starting" ? "wait" : "bad");
    $("queue").textContent = S.scored + " scored · " + S.queue.length + " waiting";
  }

  function renderField() {
    const list = $("field-list"), now = Date.now();
    list.replaceChildren();
    const lobesOnly = $("lobes-only").checked;
    const rows = S.recent.filter((r) => !lobesOnly || !r.reasons.length).slice(-40).reverse();
    if (!rows.length) { list.append(el("li", "empty", "the bee is flying out. first pools land in a few seconds.")); return; }
    for (const r of rows) {
      const fresh = Date.now() - r.t < 2500 ? " fresh" + (r.verdict === "PASS" ? " pass" : "") : "";
      const li = el("li", "row" + fresh + (selected && selected.pair === r.pair ? " sel" : ""));
      const btn = el("button", "row-btn");
      btn.type = "button";
      btn.setAttribute("aria-label", "$" + r.symbol + ", " + r.verdict.toLowerCase() + ", liquidity " + usd(r.liq));
      const sn = S.field.get(r.pair) || {};
      btn.append(el("span", "sym", "$" + r.symbol), el("span", "dim", age(now, sn.created_ms)), el("span", "num", usd(r.liq)),
        el("span", "chip " + vclass(r.verdict), r.verdict.toLowerCase()),
        el("span", "why", r.reasons.length ? r.reasons[0] : r.took ? "bee in" : "score " + r.comb.toFixed(2)));
      btn.addEventListener("click", () => { selected = r; follow = false; renderAll(); brain.fire(r); });
      li.append(btn);
      list.append(li);
    }
  }

  function renderFocus() {
    const r = selected;
    $("follow").setAttribute("aria-pressed", String(follow));
    if (!r) { $("focus-name").textContent = "waiting for the first pool"; $("senses").replaceChildren(); $("vector").replaceChildren(); return; }
    const sn = S.field.get(r.pair) || {};
    $("focus-name").textContent = "$" + r.symbol;
    $("focus-sub").textContent = (r.name || "") + " · " + age(Date.now(), sn.created_ms) + " old · liq " + usd(sn.liq || r.liq) +
      " · price " + (sn.price || r.price).toPrecision(4);
    const v = $("focus-verdict");
    v.textContent = r.verdict; v.className = "verdict " + vclass(r.verdict);
    $("focus-why").textContent = r.reasons.length ? "reflex: " + r.reasons.join(", ") : (r.flag ? "pass with a flag: antennal below 0.50" :
      r.explore ? "explore entry, small size" : "score " + r.comb.toFixed(2) + (r.took ? " · the bee went in" : ""));
    const link = $("chart"), u = safeUrl(sn.url || r.url);
    if (u) { link.href = u; link.hidden = false; } else link.hidden = true;
    const ca = $("copy-ca");
    ca.hidden = !r.token; ca.dataset.ca = r.token || "";
    if (v.dataset.pair !== r.pair) { v.dataset.pair = r.pair; v.classList.remove("focus-flash"); void v.offsetWidth; v.classList.add("focus-flash"); }
    const senses = $("senses");
    senses.replaceChildren();
    for (const f of C.FEATS) {
      const val = r.obs[f], row = el("div", "sense");
      row.append(el("span", "lab", B.LIVE_LABELS[f]));
      if (f === "bundle") row.append(el("span", val > 0.5 ? "tripped" : "clear", val > 0.5 ? "tripped" : "clear"));
      else {
        const bar = el("span", "meter"), fill = el("i");
        fill.style.width = (val * 100).toFixed(0) + "%";
        bar.append(fill); row.append(bar, el("span", "num", val.toFixed(2)));
      }
      senses.append(row);
    }
    const nr = el("div", "sense noise");
    const nb = el("span", "meter"), nf = el("i"); nf.style.width = (r.noise * 100).toFixed(0) + "%"; nb.append(nf);
    nr.append(el("span", "lab", "noise"), nb, el("span", "num", r.noise.toFixed(2)));
    senses.append(nr);
    const vec = $("vector");
    vec.replaceChildren();
    const notes = { mushroom: "seen " + r.vector.mushroom.seen + ", printed " + r.vector.mushroom.printed,
      antennal: r.vector.antennal.value < 0.45 ? "noisy input" : "clean input",
      optic: r.obs.accel > 0.55 ? "accelerating" : "flat", central: r.vector.central.mode };
    for (const k of ["mushroom", "antennal", "optic", "central"]) {
      const val = r.vector[k].value, row = el("div", "lobe-row " + k);
      const bar = el("span", "meter"), fill = el("i"); fill.style.width = (val * 100).toFixed(0) + "%"; bar.append(fill);
      row.append(el("span", "lab", k), bar, el("span", "num", val.toFixed(2)), el("span", "note", notes[k]));
      vec.append(row);
    }
    $("consensus").textContent = "consensus " + r.vector.consensus.toFixed(2) + (r.vector.consensus > 0.6 ? " · lobes agree" : " · lobes argue");
    const canBuy = S.field.has(r.pair) && !r.reasons.includes("no pool liquidity yet, bonding curve");
    for (const b of document.querySelectorAll("[data-buy]")) b.disabled = !canBuy || S.accounts.you.cash < 1;
  }

  const NAMES = { bee: "the bee", random: "random baseline", you: "you" };
  function spark(hist, w, h) {
    if (hist.length < 2) return "";
    const ys = hist.map((p) => p[1]), lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
    return hist.map((p, i) => (i ? "L" : "M") + (i / (hist.length - 1) * w).toFixed(1) + "," + (h - (p[1] - lo) / span * h).toFixed(1)).join(" ");
  }

  function renderRace() {
    const wrap = $("race");
    wrap.replaceChildren();
    const lead = Object.values(S.accounts).reduce((a, b) => (b.equity > a.equity ? b : a));
    for (const k of ["bee", "random", "you"]) {
      const a = S.accounts[k], st = a.stats(), up = st.equity >= a.start;
      const card = el("div", "acct " + k + (a === lead && S.scored > 0 ? " lead" : ""));
      const top = el("div", "acct-top");
      top.append(el("span", "acct-name", NAMES[k]), el("span", "acct-pct " + (up ? "up" : "down"), B.pct(st.equity / a.start - 1, 1)));
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 120 28"); svg.setAttribute("class", "sparkline"); svg.setAttribute("aria-hidden", "true");
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", spark(a.hist.concat([[Date.now(), a.equity]]), 120, 28));
      svg.append(path);
      card.append(top, el("div", "acct-eq", money(st.equity)), svg,
        el("div", "acct-meta", st.trades + " trades · " + st.wins + " won · " + st.open + " open · dd " + (st.max_drawdown * 100).toFixed(0) + "%"));
      wrap.append(card);
    }
    const pos = $("positions");
    pos.replaceChildren();
    const open = [];
    for (const k of ["you", "bee", "random"]) for (const p of S.accounts[k].open) open.push([k, p]);
    if (!open.length) pos.append(el("li", "empty", "no open positions"));
    for (const [k, p] of open) {
      const r = p.ret(), li = el("li", "pos");
      li.append(el("span", "who " + k, k), el("span", "sym", "$" + p.symbol), el("span", "dim", "$" + p.size.toFixed(0)),
        el("span", "num " + (r >= 0 ? "up" : "down"), B.pct(r)));
      if (k === "you") {
        const b = el("button", "mini", "sell");
        b.type = "button"; b.setAttribute("aria-label", "sell " + p.symbol);
        b.addEventListener("click", () => { S.sell(p.id, Date.now()); save(); renderAll(); });
        li.append(b);
      } else li.append(el("span", "mini ghost", Math.max(0, C.MAX_HOLD_MIN - (Date.now() - p.t0) / 60000).toFixed(0) + "m"));
      pos.append(li);
    }
  }

  function renderForward() {
    const fw = S.forward(), tb = $("fwd-body");
    tb.replaceChildren();
    for (const v of ["PASS", "WATCH", "SKIP"]) {
      const f = fw[v], tr = el("tr");
      const tv = el("td"); tv.append(el("span", "chip " + vclass(v), v.toLowerCase()));
      tr.append(tv, el("td", "", String(f.n)), el("td", "", f.n ? (f.hit * 100).toFixed(0) + "%" : "-"),
        el("td", f.n ? (f.avg_net >= 0 ? "up" : "down") : "", f.n ? B.pct(f.avg_net, 1) : "-"));
      tb.append(tr);
    }
    $("fwd-pending").textContent = S.shadows.length + " waiting for their " + C.HORIZON_MIN + " minutes · " + S.fwdDropped + " dropped";
    const g = S.gate(), gl = $("gate-list");
    $("gate-state").textContent = g.open ? "open: the bee has earned a look at real money" : "closed: paper only";
    $("gate").className = "panel gate " + (g.open ? "open" : "closed");
    gl.replaceChildren();
    for (const [name, ok, val] of g.checks) {
      const li = el("li", ok ? "ok" : "");
      li.append(el("span", "tick", ok ? "✓" : "·"), el("span", "", name), el("span", "num", val));
      gl.append(li);
    }
    const b = S.brain;
    $("memory").textContent = "sugar " + b.sugar + " · punishment " + b.pain + " · explore " + (b.eps * 100).toFixed(0) + "% · " + b.memory.length + " patterns";
  }

  function renderLog() {
    const ul = $("log");
    ul.replaceChildren();
    for (const [t, msg, tone] of S.log.slice(-14).reverse()) {
      const li = el("li", "t-" + tone);
      li.append(el("span", "dim", new Date(t).toTimeString().slice(0, 5)), el("span", "", msg));
      ul.append(li);
    }
  }

  // --------------------------------------------------------------- brain
  const brain = (function () {
    const cv = $("brain"), ctx = cv.getContext("2d");
    const REG = { optic: [[-28, 1, 8, 8], [28, 1, 8, 8]], mushroom: [[-17, -7, 4, 2], [-6, -8, 3, 2], [6, -8, 3, 2], [17, -7, 4, 2]],
      central: [[0, -1, 8, 2]], antennal: [[-8, 6, 5, 2], [8, 6, 5, 2]], motor: [[0, 10, 6, 2]] };
    const COL = { optic: [157, 124, 255], mushroom: [255, 79, 163], central: [196, 168, 255], antennal: [143, 132, 255], motor: [255, 84, 104] };
    const TR = [["antennal", -9, 4, -16, -5], ["antennal", 9, 4, 16, -5], ["optic", -21, -3, -20, -6], ["optic", 21, -3, 20, -6],
      ["optic", -19, 1, -9, 0], ["optic", 19, 1, 9, 0], ["mushroom", -14, -5, -6, -2], ["mushroom", 14, -5, 6, -2], ["central", 0, 1, 0, 8]];
    const rng = new B.FieldRng(11), pts = [];
    for (const [lobe, ells] of Object.entries(REG)) {
      let i = 0;
      for (const [cx, cy, rx, ry] of ells) {
        const n = Math.round(rx * ry * (lobe === "mushroom" ? 26 : 14));
        for (let k = 0; k < n; k++) {
          const a = rng.random() * Math.PI * 2, rr = Math.sqrt(rng.random());
          pts.push({ lobe, x: cx + Math.cos(a) * rr * (rx + 0.5), y: cy + Math.sin(a) * rr * (ry + 0.5), a: 0, kc: (i * 37) % C.N_KC, i: i++ });
        }
      }
    }
    const glow = document.createElement("canvas"); glow.width = glow.height = 32;
    const g2 = glow.getContext("2d"), grad = g2.createRadialGradient(16, 16, 0, 16, 16, 16);
    grad.addColorStop(0, "rgba(255,255,255,1)"); grad.addColorStop(0.25, "rgba(255,255,255,.55)"); grad.addColorStop(1, "rgba(255,255,255,0)");
    g2.fillStyle = grad; g2.fillRect(0, 0, 32, 32);
    const tint = {};
    for (const [k, c] of Object.entries(COL)) {
      const t = document.createElement("canvas"); t.width = t.height = 32; const tc = t.getContext("2d");
      tc.drawImage(glow, 0, 0); tc.globalCompositeOperation = "source-in"; tc.fillStyle = "rgb(" + c.join(",") + ")"; tc.fillRect(0, 0, 32, 32);
      tint[k] = t;
    }
    let pulses = [], queue = [], motorCol = null, W = 0, H = 0, scale = 1;
    function size() {
      const r = cv.getBoundingClientRect(), d = Math.min(2, window.devicePixelRatio || 1);
      W = r.width; H = r.height; cv.width = W * d; cv.height = H * d; ctx.setTransform(d, 0, 0, d, 0, 0);
      scale = Math.min(W / 76, H / 30);
    }
    const P = (x, y) => [W / 2 + x * scale, H / 2 + y * scale * 1.05];
    function excite(lobe, fn) { for (const p of pts) if (p.lobe === lobe) p.a = Math.max(p.a, fn(p)); }
    function stage(r, st) {
      const o = r.obs;
      if (st === "antennal") excite("antennal", (p) => o[C.FEATS[p.i % 8]] * (1 - 0.6 * r.noise) + 0.1);
      if (st === "optic") excite("optic", (p) => 0.2 + (0.5 * o.heat + 0.5 * o.accel) * (0.5 + 0.5 * Math.sin(p.y * 0.8 + p.x * 0.2)));
      if (st === "mushroom") { const act = new Set(r.act); excite("mushroom", (p) => (act.has(p.kc) || act.has((p.kc + 1) % C.N_KC) ? 1.3 : 0.08)); }
      if (st === "central") { const pos = -8 + 16 * B.clamp((r.comb - 0.3) / 0.5); excite("central", (p) => 1.2 * Math.exp(-((p.x - pos) ** 2) / 8)); }
      if (st === "motor") { motorCol = r.verdict === "PASS" ? [63, 224, 138] : r.verdict === "SKIP" ? [255, 84, 104] : [255, 176, 74]; excite("motor", () => 1.1); }
      for (const t of TR) if (t[0] === st) pulses.push({ t, u: 0 });
      $("stage").textContent = st === "motor" ? "motor: " + r.verdict : st;
    }
    function fire(r) {
      queue = ["antennal", "optic", "mushroom", "central", "motor"].map((st, i) => [performance.now() + i * (reduce ? 0 : 260), r, st]);
    }
    function frame(now) {
      while (queue.length && queue[0][0] <= now) { const [, r, st] = queue.shift(); stage(r, st); }
      ctx.clearRect(0, 0, W, H);
      ctx.globalCompositeOperation = "lighter";
      ctx.strokeStyle = "rgba(176,48,111,.35)"; ctx.lineWidth = 1;
      for (const t of TR) { const a = P(t[1], t[2]), b = P(t[3], t[4]); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }
      for (const p of pts) {
        const floor = p.lobe === "mushroom" ? 0.12 : 0.2;
        p.a = Math.max(floor, p.a * 0.955);
        if (!reduce && Math.random() < 0.004) p.a = Math.max(p.a, 0.5);
        const [x, y] = P(p.x, p.y), s = 3 + p.a * 9;
        ctx.globalAlpha = Math.min(1, 0.25 + p.a * 0.75);
        const img = p.lobe === "motor" && motorCol && p.a > 0.4 ? null : tint[p.lobe];
        if (img) ctx.drawImage(img, x - s / 2, y - s / 2, s, s);
        else { ctx.fillStyle = "rgb(" + motorCol.join(",") + ")"; ctx.beginPath(); ctx.arc(x, y, s / 4, 0, 7); ctx.fill(); }
        if (p.a > 0.9) { ctx.globalAlpha = (p.a - 0.9) * 4; ctx.drawImage(glow, x - 4, y - 4, 8, 8); }
      }
      ctx.globalAlpha = 1;
      pulses = pulses.filter((q) => (q.u += reduce ? 1 : 0.035) < 1);
      for (const q of pulses) {
        const a = P(q.t[1], q.t[2]), b = P(q.t[3], q.t[4]), x = a[0] + (b[0] - a[0]) * q.u, y = a[1] + (b[1] - a[1]) * q.u;
        ctx.drawImage(glow, x - 7, y - 7, 14, 14);
      }
      ctx.globalCompositeOperation = "source-over";
      requestAnimationFrame(frame);
    }
    size(); window.addEventListener("resize", size); requestAnimationFrame(frame);
    return { fire };
  })();

  // --------------------------------------------------------------- dance
  (function dance() {
    const cv = $("dance"), ctx = cv.getContext("2d"), d = Math.min(2, window.devicePixelRatio || 1);
    cv.width = 120 * d; cv.height = 120 * d; ctx.setTransform(d, 0, 0, d, 0, 0);
    let t = 0;
    const trail = [];
    // same figure eight as the terminal: straight run down the middle, return loops on alternate sides
    function xy(t, comb, cons) {
      const s = t % (2 * Math.PI), run = 0.35 + 0.65 * B.clamp((comb - 0.3) / 0.5), rp = Math.PI * 0.8;
      if (s < rp) { const u = s / rp; return [0.22 * (1.1 - cons) * Math.sin(u * 26), run * (1 - 2 * u)]; }
      const u = (s - rp) / (2 * Math.PI - rp), side = Math.floor(t / (2 * Math.PI)) % 2 ? -1 : 1;
      return [side * 0.9 * Math.sin(Math.PI * u), -run + 2 * run * u];
    }
    function frame() {
      const r = selected, comb = r ? r.comb : 0.5, cons = r ? r.vector.consensus : 0.5;
      t += reduce ? 0 : 0.05;
      const p = xy(t, comb, cons);
      trail.push([60 + p[0] * 50, 60 - p[1] * 50]); if (trail.length > 70) trail.shift();
      ctx.clearRect(0, 0, 120, 120);
      ctx.fillStyle = "rgba(176,48,111,.35)";
      for (let k = 0; k < 160; k++) { const q = xy(Math.floor(t / (4 * Math.PI)) * 4 * Math.PI + k / 160 * 4 * Math.PI, comb, cons); ctx.fillRect(60 + q[0] * 50, 60 - q[1] * 50, 1.2, 1.2); }
      trail.forEach(([x, y], i) => { ctx.fillStyle = "rgba(255,175,215," + (i / trail.length).toFixed(2) + ")"; ctx.beginPath(); ctx.arc(x, y, 1 + 2 * i / trail.length, 0, 7); ctx.fill(); });
      const [hx, hy] = trail[trail.length - 1];
      ctx.fillStyle = "#f3efe6"; ctx.beginPath(); ctx.arc(hx, hy, 3.5, 0, 7); ctx.fill();
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  })();

  // --------------------------------------------------------------- share
  function shareCard() {
    const W = 1200, H = 630, cv = document.createElement("canvas"); cv.width = W; cv.height = H;
    const c = cv.getContext("2d");
    c.fillStyle = "#000"; c.fillRect(0, 0, W, H);
    const g = c.createRadialGradient(980, 150, 20, 980, 150, 520); g.addColorStop(0, "rgba(255,79,163,.22)"); g.addColorStop(1, "rgba(255,79,163,0)");
    c.fillStyle = g; c.fillRect(0, 0, W, H);
    const grad = c.createLinearGradient(60, 0, 520, 0); grad.addColorStop(0, "#f3efe6"); grad.addColorStop(0.7, "#ffafd7"); grad.addColorStop(1, "#ff4fa3");
    c.fillStyle = grad; c.font = "700 72px Cinzel, serif"; c.fillText("BeeBrain", 60, 120);
    c.fillStyle = "#a09caa"; c.font = "22px 'JetBrains Mono', monospace";
    const mins = Math.max(1, (Date.now() - S.started) / 60000);
    c.fillText("the field · " + S.chain + " · " + S.scored + " live pools · " + (mins < 120 ? mins.toFixed(0) + " min" : (mins / 60).toFixed(1) + " h"), 62, 165);
    const rows = [["the bee", S.accounts.bee, "#ff4fa3"], ["random baseline", S.accounts.random, "#a09caa"], ["me", S.accounts.you, "#ffb04a"]];
    rows.forEach(([name, a, col], i) => {
      const y = 260 + i * 92, e = a.equity, m = e / a.start - 1;
      c.fillStyle = col; c.font = "700 26px 'Space Grotesk', sans-serif"; c.fillText(name, 62, y);
      c.fillStyle = "#f3efe6"; c.font = "700 54px 'Space Grotesk', sans-serif"; c.fillText(money(e), 330, y + 8);
      c.fillStyle = m >= 0 ? "#3fe08a" : "#ff6b7e"; c.font = "700 30px 'JetBrains Mono', monospace"; c.fillText(B.pct(m, 1), 620, y + 4);
    });
    const fw = S.forward();
    c.fillStyle = "#f3efe6"; c.font = "700 26px 'Space Grotesk', sans-serif"; c.fillText("forward test, +15 min", 820, 250);
    c.font = "24px 'JetBrains Mono', monospace";
    ["PASS", "WATCH", "SKIP"].forEach((v, i) => {
      const f = fw[v], y = 300 + i * 46;
      c.fillStyle = v === "PASS" ? "#3fe08a" : v === "WATCH" ? "#ffb04a" : "#ff6b7e"; c.fillText(v.toLowerCase(), 820, y);
      c.fillStyle = "#dcd8cf"; c.fillText(f.n ? f.n + " · " + B.pct(f.avg_net, 1) : "waiting", 950, y);
    });
    c.fillStyle = "#6f6b78"; c.font = "18px 'JetBrains Mono', monospace";
    c.fillText("paper money on real prices. not financial advice.", 62, 585);
    c.fillText("github.com/h100envy/beebrain", 820, 585);
    cv.toBlob((blob) => {
      const a = el("a"); a.href = URL.createObjectURL(blob); a.download = "beebrain-race-" + S.chain + ".png";
      document.body.append(a); a.click(); a.remove();
    });
  }

  // ------------------------------------------------------------- actions
  function buy(usdAmt) {
    if (!selected) return;
    const p = S.buy(selected.pair, usdAmt, Date.now());
    $("buy-note").textContent = p ? "bought $" + p.symbol + " for $" + p.size.toFixed(0) + " of paper. filled at " +
      p.fill.toPrecision(4) + " after impact." : "no price for this pool right now";
    save(); renderAll();
  }

  function exportCsv() {
    const rows = ["day,token,size_usd,pnl_pct"];
    for (const c of S.accounts.you.closed) {
      rows.push([Math.floor((c.t1 - S.started) / 86400000) + 1, "$" + String(c.symbol).replace(/[,\n]/g, ""), c.size.toFixed(2), (c.ret * 100).toFixed(2)].join(","));
    }
    const a = el("a");
    a.href = URL.createObjectURL(new Blob([rows.join("\n") + "\n"], { type: "text/csv" }));
    a.download = "beebrain-" + S.chain + "-trades.csv";
    document.body.append(a); a.click(); a.remove();
  }

  function wire() {
    for (const b of document.querySelectorAll("[data-chain]")) b.addEventListener("click", () => start(b.dataset.chain));
    for (const b of document.querySelectorAll("[data-buy]")) b.addEventListener("click", () => buy(Number(b.dataset.buy)));
    $("follow").addEventListener("click", () => { follow = !follow; if (follow && S.last) selected = S.last; renderAll(); });
    $("export").addEventListener("click", exportCsv);
    $("share").addEventListener("click", shareCard);
    const lo = $("lobes-only");
    lo.checked = store.get("beebrain.field.lobesOnly") === "1";
    lo.addEventListener("change", () => { store.set("beebrain.field.lobesOnly", lo.checked ? "1" : "0"); renderField(); });
    $("copy-ca").addEventListener("click", () => copyCa($("copy-ca").dataset.ca, $("copy-ca")));
    const nb = $("notify");
    nb.setAttribute("aria-pressed", String(notifyOn));
    nb.addEventListener("click", async () => {
      if (!notifyOn && "Notification" in window && Notification.permission !== "granted") {
        const p = await Notification.requestPermission();
        if (p !== "granted") { nb.textContent = "notifications blocked"; return; }
      }
      notifyOn = !notifyOn; store.set("beebrain.field.notify", notifyOn ? "1" : "0"); nb.setAttribute("aria-pressed", String(notifyOn));
    });
    if (!store.get("beebrain.field.intro")) $("intro").hidden = false;
    $("intro-close").addEventListener("click", () => { $("intro").hidden = true; store.set("beebrain.field.intro", "1"); });
    $("reset").addEventListener("click", () => {
      const now = Date.now();
      if (now - resetArmed > 4000) { resetArmed = now; $("reset").textContent = "click again to reset"; return; }
      store.del(KEY(S.chain)); S = null; start(chain); $("reset").textContent = "reset this bee";
    });
    document.addEventListener("keydown", (e) => {
      if (e.target.closest && e.target.closest("input,textarea")) return;
      if (e.key === "b") buy(50);
    });
    document.addEventListener("visibilitychange", () => { if (document.hidden) save(); });
    window.addEventListener("pagehide", save);
  }

  wire();
  start(chain);
  setInterval(tick, 250);
})();
