"""
a field session: the bee on real pools, three paper accounts and a forward test.

  you      your own paper trades
  bee      the bee on autopilot: it enters what it passes, sized like the sim
  random   a baseline that enters random pools at the bee's own entry rate,
           behind the same reflexes, with the same sizing and exits. if the bee
           cannot beat this, its learned part is worth nothing yet.

every pool the bee scores is also written into the forward test: its price when
scored, and its price after HORIZON_MIN minutes. that gives a hit rate per verdict
on the real market, whether or not anybody traded. skipped pools teach the brain
through the same ghost channel the sim uses. closed bee trades broadcast sugar or
punishment.
"""
from collections import deque

from ..brain import GHOST_LR, BeeBrain, waggle_vector
from ..engine import MAX_OPEN, SIZE_EXPLORE, SIZE_PASS
from .features import FieldPool, features
from .paper import Account
from .rng import FieldRng

HORIZON_MIN = 15.0
FWD_FEE = 0.02                  # round trip, same as the sim
DROP_AFTER_MIN = 20.0           # a forward test with no price this long after its horizon is dropped
MAX_AGE_DAYS = 30.0             # older pairs are not launches any more
MAX_FDV = 200e6
FIELD_TTL_MIN = 90.0
RANDOM_MIN_RATE = 0.08
GRADUATE_POOLS = 300            # forward tested pools before the gate can open
GRADUATE_EDGE = 0.05            # PASS must beat SKIP by this much average net return
SEED = 5


class FieldSession:
    def __init__(self, chain="solana", seed=SEED, horizon_min=HORIZON_MIN):
        self.chain = chain
        self.seed = seed
        self.horizon_min = horizon_min
        self.rng = FieldRng(seed)
        self.brain = BeeBrain(self.rng)
        self.rrand = FieldRng(seed * 7 + 99)
        self.accounts = {k: Account(k) for k in ("you", "bee", "random")}
        self.field = {}                  # pair -> latest snapshot
        self.seen = set()
        self.queue = deque()
        self.recent = deque(maxlen=60)   # scored pools, newest last
        self.shadows = []                # pending forward tests
        self.fwd = {v: {"n": 0, "wins": 0, "net": 0.0} for v in ("PASS", "WATCH", "SKIP")}
        self.fwd_recent = deque(maxlen=200)
        self.fwd_dropped = 0
        self.fwd_log = []                # every resolved forward test, for reports
        self.counts = {"PASS": 0, "WATCH": 0, "SKIP": 0}
        self.scored = 0
        self.bee_takes = 0
        self.reflexed = 0
        self.log = deque(maxlen=60)
        self.last = None                 # the last scored record

    # ------------------------------------------------------------ log ---
    def say(self, t_ms, msg, tone="dim"):
        self.log.append((t_ms, msg, tone))

    # ---------------------------------------------------------- field ---
    def eligible(self, s, now_ms):
        if s.get("chain") != self.chain or s.get("price", 0) <= 0 or not s.get("pair"):
            return False
        if s.get("created_ms") and (now_ms - s["created_ms"]) / 86400000.0 > MAX_AGE_DAYS:
            return False
        return s.get("fdv", 0) <= MAX_FDV

    def ingest(self, snaps, now_ms):
        """new snapshots from any feed. unseen pairs join the queue."""
        added = 0
        for s in snaps:
            s = dict(s)
            s.setdefault("t_ms", now_ms)
            if s.get("pair") in self.field or self.eligible(s, now_ms):
                self.field[s["pair"]] = s
            if s.get("pair") and s["pair"] not in self.seen and self.eligible(s, now_ms):
                self.seen.add(s["pair"])
                self.queue.append(s["pair"])
                added += 1
        keep = self.tracked(10 ** 6)
        cutoff = now_ms - FIELD_TTL_MIN * 60000
        for pair in [p for p, s in self.field.items() if s["t_ms"] < cutoff and p not in keep and p not in self.queue]:
            del self.field[pair]
        return added

    def tracked(self, limit=30):
        """pairs whose price matters now: open positions first, then forward tests by due time"""
        out = []
        for a in self.accounts.values():
            for p in a.open:
                if p.pair not in out:
                    out.append(p.pair)
        for sh in sorted(self.shadows, key=lambda s: s["due"]):
            if sh["pair"] not in out:
                out.append(sh["pair"])
        return out[:limit]

    # ---------------------------------------------------------- score ---
    def score_next(self, now_ms):
        while self.queue:
            pair = self.queue.popleft()
            s = self.field.get(pair)
            if s:
                return self.score(s, now_ms)
        return None

    def score(self, s, now_ms):
        vols = [x["vol_h1"] for x in self.field.values()]
        obs, noise, reasons = features(s, vols, now_ms)
        self.scored += 1
        pool = FieldPool(s, obs, noise, reasons, self.scored)
        t = self.brain.think(pool, None)
        v = t["verdict"]
        self.counts[v] += 1
        if reasons:
            self.reflexed += 1
        vec = waggle_vector(pool, t)
        rec = {"n": self.scored, "t": now_ms, "pair": s["pair"], "symbol": s["symbol"], "name": s["name"],
               "url": s.get("url", ""), "price": s["price"], "liq": s["liq"], "obs": obs, "noise": noise,
               "reasons": reasons, "verdict": v, "comb": t["comb"], "take": t["take"], "explore": t["explore"],
               "flag": t["flag"], "vector": vec, "act": sorted(t["act"])}
        took = False
        bee = self.accounts["bee"]
        if t["take"] and len(bee.open) < MAX_OPEN:
            size = bee.equity * (SIZE_EXPLORE if t["explore"] else SIZE_PASS)
            if bee.buy(s, size, now_ms, t["act"], "explore" if t["explore"] else "pass"):
                took = True
                self.bee_takes += 1
                self.say(now_ms, "bee %s %s $%.0f  mb %.2f" % ("explores" if t["explore"] else "enters",
                                                               pool.name, size, t["lobes"]["mushroom"]), "entry")
        rand = self.accounts["random"]
        rate = max(RANDOM_MIN_RATE, self.bee_takes / self.scored)
        if not reasons and self.rrand.random() < rate and len(rand.open) < MAX_OPEN:
            rand.buy(s, rand.equity * SIZE_PASS, now_ms, None, "random")
        if reasons and self.rrand.random() < 0.3:
            self.say(now_ms, "%s reflex: %s" % (pool.name, reasons[0]), "dim")
        self.shadows.append({"pair": s["pair"], "symbol": s["symbol"], "t0": now_ms, "p0": s["price"],
                             "due": now_ms + self.horizon_min * 60000, "verdict": v, "act": rec["act"], "took": took,
                             "comb": t["comb"], "obs": obs, "noise": noise, "reasons": reasons, "liq": s["liq"]})
        rec["took"] = took
        self.recent.append(rec)
        self.last = rec
        return rec

    # ----------------------------------------------------------- mark ---
    def mark(self, now_ms):
        for name, a in self.accounts.items():
            for c in a.mark(self.field, now_ms):
                won = c["pnl"] > 0
                if name == "bee":
                    self.brain.after_trade(frozenset(c["act"]), won)
                    self.say(now_ms, "bee closed $%s %+.0f%%, %s. %s" % (
                        c["symbol"], c["ret"] * 100, c["reason"], "sugar" if won else "punishment"), "good" if won else "bad")
                elif name == "you":
                    self.say(now_ms, "you closed $%s %+.0f%%, %s" % (c["symbol"], c["ret"] * 100, c["reason"]),
                             "good" if won else "bad")
        keep = []
        for sh in self.shadows:
            s = self.field.get(sh["pair"])
            if now_ms < sh["due"]:
                keep.append(sh)
            elif s and s["t_ms"] >= sh["due"] and s["price"] > 0 and sh["p0"] > 0:
                self.resolve(sh, s["price"])
            elif now_ms - sh["due"] > DROP_AFTER_MIN * 60000:
                self.fwd_dropped += 1
            else:
                keep.append(sh)
        self.shadows = keep

    def resolve(self, sh, price):
        ret = price / sh["p0"] - 1
        net = (1 + ret) * (1 - FWD_FEE) - 1
        won = net > 0
        f = self.fwd[sh["verdict"]]
        f["n"] += 1
        f["wins"] += 1 if won else 0
        f["net"] += net
        self.fwd_recent.append((sh["symbol"], sh["verdict"], net))
        if len(self.fwd_log) < 20000:
            self.fwd_log.append({k: sh.get(k) for k in ("symbol", "pair", "verdict", "comb", "obs", "noise", "reasons", "liq", "took", "t0")}
                                | {"net": net, "ret": ret})
        if not sh["took"]:
            act = frozenset(sh["act"])
            self.brain.learn(act, won, GHOST_LR)
            self.brain.memory.append((act, 1 if won else 0))

    # ----------------------------------------------------------- you ---
    def buy(self, pair, usd, now_ms):
        s = self.field.get(pair)
        if not s:
            return None
        pos = self.accounts["you"].buy(s, usd, now_ms, None, "manual")
        if pos:
            self.say(now_ms, "you bought $%s $%.0f" % (s["symbol"], pos.size), "entry")
        return pos

    def sell(self, pos_id, now_ms):
        you = self.accounts["you"]
        for p in you.open:
            if p.id == pos_id:
                c = you.close(p, now_ms, "manual")
                self.say(now_ms, "you sold $%s %+.0f%%" % (c["symbol"], c["ret"] * 100), "good" if c["pnl"] > 0 else "bad")
                return c
        return None

    # --------------------------------------------------------- report ---
    def forward(self):
        out = {}
        for v, f in self.fwd.items():
            out[v] = {"n": f["n"], "hit": f["wins"] / f["n"] if f["n"] else 0.0, "avg_net": f["net"] / f["n"] if f["n"] else 0.0}
        return out

    def gate(self):
        """when the bee has earned a look at real money: enough pools, PASS beats SKIP, bee beats random"""
        fw = self.forward()
        n = sum(f["n"] for f in fw.values())
        edge = fw["PASS"]["avg_net"] - fw["SKIP"]["avg_net"] if fw["PASS"]["n"] and fw["SKIP"]["n"] else 0.0
        bee, rnd = self.accounts["bee"].equity, self.accounts["random"].equity
        checks = [("forward tested pools", n >= GRADUATE_POOLS, "%d of %d" % (n, GRADUATE_POOLS)),
                  ("PASS beats SKIP", edge >= GRADUATE_EDGE, "%+.1f%% of %+.0f%%" % (edge * 100, GRADUATE_EDGE * 100)),
                  ("bee beats random", bee > rnd, "$%.0f vs $%.0f" % (bee, rnd))]
        return {"open": all(c[1] for c in checks), "checks": checks}

    # ---------------------------------------------------------- state ---
    def to_json(self):
        b = self.brain
        return {
            "v": 1, "chain": self.chain, "seed": self.seed, "horizon_min": self.horizon_min,
            "rng": self.rng.state(), "rrand": self.rrand.state(),
            "brain": {"w": b.w, "eps": b.eps, "resolved": b.resolved, "sugar": b.sugar, "pain": b.pain,
                      "memory": [[sorted(a), w] for a, w in list(b.memory)[-300:]]},
            "accounts": {k: a.to_json() for k, a in self.accounts.items()},
            "shadows": self.shadows, "fwd": self.fwd, "fwd_dropped": self.fwd_dropped,
            "counts": self.counts, "scored": self.scored, "bee_takes": self.bee_takes, "reflexed": self.reflexed,
            "seen": list(self.seen)[-3000:],
        }

    @classmethod
    def from_json(cls, d):
        s = cls(d["chain"], d["seed"], d.get("horizon_min", HORIZON_MIN))
        s.rng = FieldRng.from_state(d["rng"])
        s.brain.rng = s.rng
        s.rrand = FieldRng.from_state(d["rrand"])
        b = d["brain"]
        s.brain.w, s.brain.eps, s.brain.resolved = b["w"], b["eps"], b["resolved"]
        s.brain.sugar, s.brain.pain = b["sugar"], b["pain"]
        for a, w in b["memory"]:
            s.brain.memory.append((frozenset(a), w))
        s.accounts = {k: Account.from_json(v) for k, v in d["accounts"].items()}
        s.shadows, s.fwd, s.fwd_dropped = d["shadows"], d["fwd"], d["fwd_dropped"]
        s.counts, s.scored, s.bee_takes, s.reflexed = d["counts"], d["scored"], d["bee_takes"], d["reflexed"]
        s.seen = set(d["seen"])
        return s
