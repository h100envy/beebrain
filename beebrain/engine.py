"""
beebrain.engine

a paper account around the brain. positions, fees, and the broadcast of every closed
trade back into memory: a print on the octopamine channel, a loss on the punishment
channel. no keys, no signatures, no orders. every trade here is simulated.

stage 1 is the brain on its own. stage 2 adds a rule based reader standing in for grok.
stage 3 adds a ninth glomerulus for telegram velocity.

log lines carry a tone, not a colour. the terminal decides how a tone looks.

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import hashlib
import random
from collections import deque

from . import market
from .brain import FEATS, GHOST_LR, BeeBrain, BeeBrain9, clamp
from .market import VEL_HI, AGE_OLD, Pool, step_heat

START_CASH = 500.0
POOLS_PER_DAY = 40
FEE = 0.02                    # round trip, charged once on close
MAX_OPEN = 4
SIZE_PASS = 0.13              # share of equity on a pass
SIZE_EXPLORE = 0.04           # share of equity on an explore entry
MIN_SIZE = 5.0
LIFE = (8, 26)                # pools a position stays open
PATH_VOL = 0.16
HOLD_WARN = -0.30             # log once when an open position is this far under

# stage 2
GROK_START = 1300.0
DIRTY = 0.50                  # antennal below this = raw data is dirty
STRONG_MB = 0.52              # memory leans yes
STRONG_OL = 0.56              # market shape leans yes
DETECT = 0.80                 # a re-read catches a rug in progress this often
FALSE_ALARM = 0.12            # a clean pool looks scary on re-read this often
WARM_DAYS = 9                 # stage 1 memory replayed before stage 2 starts

# stage 3
TG_START = 600.0
INSIGHT_EVERY = 120
SURFACE_EVERY = 25

USERS = ["anon_418", "degen_kid", "sol_maxi", "wenmoon", "0xlurker", "rugsurvivor", "pumpfun_pete",
         "chart_monk", "ser_ape", "lowcap_larry", "mev_mary", "bagholder"]
TG_LINES = ["gm", "ca?", "dev doxxed?", "lp locked", "who is buying", "send it", "chart looks clean",
            "bundled?", "early", "dev sold?", "mods asleep", "raid now", "wen cex", "holders up", "ser"]


def money(v):
    return "${:,.0f}".format(v)


class Position:
    def __init__(self, rng, pool, size, act, explore, opened):
        self.pool, self.size, self.act, self.explore = pool, size, act, explore
        self.won = rng.random() < pool.p_win
        self.final = rng.uniform(*market.WIN_RANGE) if self.won else -rng.uniform(*market.LOSS_RANGE)
        self.life = rng.randint(*LIFE)
        self.opened = opened
        # brownian bridge path, so winners can dip hard before they print
        steps = [0.0]
        for _ in range(self.life):
            steps.append(steps[-1] + rng.gauss(0, PATH_VOL))
        self.path = [self.final * t / self.life + steps[t] - steps[-1] * t / self.life
                     for t in range(self.life + 1)]
        self.path = [max(-0.95, v) for v in self.path]
        self.age = 0
        self.min = 0.0
        self.warned = False

    @property
    def ret(self):
        return self.path[min(self.age, self.life)]


class FixedPosition(Position):
    """outcome is fixed when the pool is born, so a wait can be scored against entering now."""

    def __init__(self, rng, pool, size, act, explore, opened, final=None):
        super().__init__(rng, pool, size, act, explore, opened)
        self.final = pool.final if final is None else final
        self.won = self.final > 0
        steps = [0.0]
        for _ in range(self.life):
            steps.append(steps[-1] + rng.gauss(0, PATH_VOL))
        self.path = [max(-0.95, self.final * t / self.life + steps[t] - steps[-1] * t / self.life)
                     for t in range(self.life + 1)]
        if pool.rug:                      # rugs go straight down
            self.life = min(self.life, 6)
            self.path = [self.final * min(1, t / 3) for t in range(self.life + 1)]


class Engine:
    def __init__(self, seed, record=False):
        self.seed = seed
        self.rng = random.Random(seed)
        self.brain = BeeBrain(self.rng)
        self.n = 0
        self.start = START_CASH
        self.cash = START_CASH
        self.open = []
        self.closed = []                  # (name, pnl, final, min, explore)
        self.equity_hist = deque([START_CASH], maxlen=400)
        self.peak = START_CASH
        self.max_dd = 0.0
        self.heat = market.HEAT_START
        self.heat_hist = deque([market.HEAT_START] * market.HEAT_HIST, maxlen=market.HEAT_HIST)
        self.log = deque(maxlen=40)
        self.events = [] if record else None
        self.pool = None
        self.thought = None
        self.counts = {"PASS": 0, "WATCH": 0, "SKIP": 0}
        self.hold_saves = 0

    @property
    def equity(self):
        return self.cash + sum(p.size * (1 + p.ret) for p in self.open)

    @property
    def day(self):
        return self.n // POOLS_PER_DAY + 1

    def stamp(self):
        m = int((self.n % POOLS_PER_DAY) / POOLS_PER_DAY * 1440)
        return "d%d %02d:%02d" % (self.day, m // 60, m % 60)

    def say(self, s, tone="dim"):
        self.log.append((self.stamp(), s, tone))
        if self.events is not None:
            self.events.append("%d|%s|%s" % (self.n, s, tone))

    def step(self):
        """one pool, start to finish. the terminal runs the same three calls, spread over frames."""
        self.next_pool()
        self.tick_positions()
        self.act()

    def next_pool(self):
        self.n += 1
        self.heat = step_heat(self.rng, self.heat)
        self.heat_hist.append(self.heat)
        accel = self.heat - self.heat_hist[-market.ACCEL_LAG]
        self.pool = Pool(self.rng, self.n, self.heat, accel)
        self.thought = self.brain.think(self.pool, self.heat_hist)

    def size_for(self, explore):
        return min(self.cash, self.equity * (SIZE_EXPLORE if explore else SIZE_PASS))

    def act(self):
        p, t = self.pool, self.thought
        self.counts[t["verdict"]] += 1
        # every pool the brain skipped still teaches it a little: it watches what happened
        if not t["take"]:
            ghost_won = self.rng.random() < p.p_win
            self.brain.learn(t["act"], ghost_won, GHOST_LR)
            self.brain.memory.append((t["act"], 1 if ghost_won else 0))
        if t["take"] and len(self.open) < MAX_OPEN:
            size = self.size_for(t["explore"])
            if size >= MIN_SIZE:
                self.cash -= size
                self.open.append(Position(self.rng, p, size, t["act"], t["explore"], self.n))
                tag = "explore" if t["explore"] else ("pass, flagged" if t["flag"] else "pass")
                self.say("%s %s %s  mb %.2f" % (p.name, tag, money(size), t["lobes"]["mushroom"]), "entry")
        elif t["verdict"] == "SKIP" and p.obs["bundle"] > 0.5 and self.rng.random() < 0.25:
            self.say("%s skip, bundled" % p.name, "dim")

    def tick_positions(self):
        still = []
        for pos in self.open:
            pos.age += 1
            r = pos.ret
            pos.min = min(pos.min, r)
            if r < HOLD_WARN and not pos.warned and pos.age < pos.life:
                pos.warned = True
                self.say("%s %+.0f%%, bee holds" % (pos.pool.name, r * 100), "bad")
            if pos.age >= pos.life:
                out = pos.size * (1 + pos.final) * (1 - FEE)
                self.cash += out
                pnl = out - pos.size
                won = pnl > 0
                # the broadcast: sugar or punishment, only to the cells that fired for this pool
                self.brain.after_trade(pos.act, won)
                self.closed.append((pos.pool.name, pnl, pos.final, pos.min, pos.explore))
                if won and pos.min < HOLD_WARN:
                    self.hold_saves += 1
                self.say("%s closed %+.0f%%  %s%s" % (pos.pool.name, pos.final * 100,
                         "+" if pnl >= 0 else "-", money(abs(pnl))), "good" if won else "bad")
            else:
                still.append(pos)
        self.open = still
        e = self.equity
        self.equity_hist.append(e)
        self.peak = max(self.peak, e)
        self.max_dd = min(self.max_dd, e / self.peak - 1)

    # ------------------------------------------------------- results ---
    def summary(self):
        n = len(self.closed)
        wins = sum(1 for c in self.closed if c[1] > 0)
        return {
            "seed": self.seed,
            "days": self.n / POOLS_PER_DAY,
            "pools": self.n,
            "start": round(self.start, 2),
            "final": round(self.equity, 2),
            "trades": n,
            "wins": wins,
            "win_rate": round(wins / n, 4) if n else 0.0,
            "max_drawdown": round(self.max_dd, 4),
            "open": len(self.open),
            "sugar": self.brain.sugar,
            "punishment": self.brain.pain,
            "verdicts": dict(self.counts),
        }

    def event_hash(self):
        return hashlib.sha256("\n".join(self.events or []).encode()).hexdigest()


def run(seed, days=9, record=True):
    """headless: the brain scores days x POOLS_PER_DAY pools and returns the engine"""
    e = Engine(seed, record=record)
    for _ in range(int(days * POOLS_PER_DAY)):
        e.step()
    return e


def parse_seeds(spec):
    """'0-9' or '1,4,7' or '3'"""
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


# ============================================================ stage 2: grok ===
class GrokEngine(Engine):
    """the bee sends the whole waggle vector. a rule based reader, standing in for grok,
    waits one cycle when memory or shape say yes but the raw data is dirty."""

    def __init__(self, seed, start=GROK_START, record=False):
        super().__init__(seed, record=record)
        self.start = self.cash = self.peak = start
        self.equity_hist = deque([start], maxlen=400)
        self.rr = random.Random(seed * 7 + 99)
        # the bee arrives with the memory it built in stage 1: nine days of pools, replayed silently
        warm = Engine(seed)
        for _ in range(WARM_DAYS * POOLS_PER_DAY):
            warm.step()
        self.brain = warm.brain
        self.heat, self.heat_hist = warm.heat, warm.heat_hist
        self.rng = warm.rng
        self.warm_pools = warm.n
        self.waiting = None
        self.grok = None
        self.ledger = deque(maxlen=40)
        self.packets = deque(maxlen=12)
        self.st = {"sent": 0, "now": 0, "waits": 0, "avoided": 0, "missed": 0, "saved": 0.0, "rugs_dodged": 0, "late": 0}

    def step(self):
        self.reread()
        super().step()

    def next_pool(self):
        super().next_pool()
        p, rr = self.pool, self.rr
        market.dirty(p, rr)
        self.thought = self.brain.think(p, self.heat_hist)
        market.settle_rug(p, rr)

    def packet_lines(self, p, t):
        L = t["lobes"]
        m, a, o, c = L["mushroom"], L["antennal"], L["optic"], L["central"]
        return [
            ("mushroom", m, "seen %d, printed %d" % (t["seen"], t["won"])),
            ("antennal", a, "raw data dirty, metrics contradict" if a < DIRTY else "input clean"),
            ("optic", o, "narrative accelerating" if p.obs["accel"] > 0.55 else "narrative flat"),
            ("central", c, "explore" if t["explore"] else ("exploit, antennal below threshold" if a < DIRTY else "exploit")),
        ]

    def act(self):
        p, t = self.pool, self.thought
        self.counts[t["verdict"]] += 1
        L = t["lobes"]
        dirty = L["antennal"] < DIRTY
        strong = L["mushroom"] >= STRONG_MB or L["optic"] >= STRONG_OL
        wait = t["verdict"] != "SKIP" and dirty and strong and self.waiting is None
        if not (t["take"] or wait) or len(self.open) >= MAX_OPEN:
            ghost_won = p.final > 0
            self.brain.learn(t["act"], ghost_won, GHOST_LR)
            self.brain.memory.append((t["act"], 1 if ghost_won else 0))
            return
        size = self.size_for(t["explore"] and not wait)
        if size < MIN_SIZE:
            return
        self.st["sent"] += 1
        pk = self.packet_lines(p, t)
        g = {"name": p.name, "packet": pk, "verdict": t["verdict"], "flag": dirty, "old": t["comb"],
             "lines": [], "decision": None}
        g["lines"].append(("packet in: 5 fields, not one number", "dim"))
        for name, v, note in pk:
            g["lines"].append(("reads %-8s %.2f  %s" % (name, v, note), "bad" if (name == "antennal" and dirty) else "text"))
        if wait:
            g["lines"].append(("memory or shape says yes, the raw data is dirty", "entry"))
            g["lines"].append(("a single %.2f would have been read as a plain %s" % (t["comb"], t["verdict"].lower()), "dim"))
            g["decision"] = ("WAIT", "one cycle, then re-read")
            self.waiting = (p, t, size)
            self.st["waits"] += 1
            self.say("%s grok waits, antennal %.2f" % (p.name, L["antennal"]), "wait")
            self.packets.append((p.name, t["comb"], L["antennal"], "WAIT"))
        else:
            g["lines"].append(("lobes agree enough, no reason to wait" if not dirty else "explore size, small enough to take", "dim"))
            g["decision"] = ("ENTER", "now, %s" % money(size))
            self.st["now"] += 1
            self.cash -= size
            self.open.append(FixedPosition(self.rng, p, size, t["act"], t["explore"], self.n))
            self.say("%s %s %s  mb %.2f" % (p.name, "explore" if t["explore"] else "enter", money(size), L["mushroom"]), "entry")
            self.packets.append((p.name, t["comb"], L["antennal"], "ENTER"))
        self.grok = g

    def reread(self):
        if not self.waiting:
            return
        p, t, size = self.waiting
        self.waiting = None
        rr = self.rr
        detect = p.rug and rr.random() < DETECT
        alarm = (not p.rug) and rr.random() < FALSE_ALARM
        now_pnl = size * ((1 + p.final) * (1 - FEE) - 1)
        g = {"name": p.name, "packet": self.packet_lines(p, t), "verdict": t["verdict"], "flag": True,
             "old": t["comb"], "lines": [("re-read after one cycle", "dim")], "decision": None}
        if detect or alarm:
            liq = rr.uniform(0.30, 0.60) if detect else rr.uniform(0.15, 0.30)
            g["lines"].append(("liquidity -%.0f%% during the wait%s" % (liq * 100, ", creator wallet moved" if detect else ""), "bad"))
            g["decision"] = ("SKIP", "not worth it after the re-read")
            grok_pnl = 0.0
            self.brain.learn(t["act"], p.final > 0, GHOST_LR)
        else:
            slip = rr.uniform(0.02, 0.07)
            fin = (1 + p.final) / (1 + slip) - 1
            g["lines"].append(("noise %.2f now, metrics agree" % (p.noise * 0.35), "good"))
            g["decision"] = ("ENTER", "%+.0f%% above the first price" % (slip * 100))
            grok_pnl = size * ((1 + fin) * (1 - FEE) - 1)
            if size <= self.cash and len(self.open) < MAX_OPEN:
                self.cash -= size
                self.open.append(FixedPosition(self.rng, p, size, t["act"], False, self.n, final=fin))
        saved = grok_pnl - now_pnl
        self.st["saved"] += saved
        skipped = g["decision"][0] == "SKIP"
        if skipped and now_pnl < 0:
            self.st["avoided"] += 1
        elif skipped and now_pnl > 0:
            self.st["missed"] += 1
        else:
            self.st["late"] += 1
        if p.rug and g["decision"][0] == "SKIP":
            self.st["rugs_dodged"] += 1
        g["lines"].append(("entering at once would have closed %+.0f%%%s" % (p.final * 100, ", it rugged" if p.rug else ""),
                           "bad" if p.final < 0 else "good"))
        g["lines"].append(("the wait: %s%s" % ("+" if saved >= 0 else "-", money(abs(saved))), "good" if saved >= 0 else "bad"))
        self.ledger.append((self.stamp(), p.name, g["decision"][0], p.final, now_pnl, grok_pnl, saved, p.rug))
        self.say("%s re-read: %s, wait %s%s" % (p.name, g["decision"][0].lower(), "+" if saved >= 0 else "-", money(abs(saved))),
                 "good" if saved >= 0 else "bad")
        self.grok = g


# ======================================================== stage 3: telegram ===
class TelegramEngine(Engine):
    def __init__(self, seed, start=TG_START, record=False):
        super().__init__(seed, record=record)
        self.brain = BeeBrain9(self.rng)
        self.start = self.cash = self.peak = start
        self.equity_hist = deque([start], maxlen=400)
        self.rr = random.Random(seed * 13 + 7)
        self.tg = {"msgs": 0, "members": 0, "links": 0, "emoji": 0.0, "vel": 0.0, "groups": 0}
        self.chat = deque(maxlen=14)
        self.room = deque(maxlen=80)          # telegram chat: dicts who, text, time, bee
        self.bee_queue = deque()
        self.last_insight = 0
        self.cells = {(h, o): [0, 0] for h in (0, 1) for o in (0, 1)}     # (vel high, creator old): [pools, wins]
        self.catches = deque(maxlen=20)
        self.surface = [[0.5] * 4 for _ in range(4)]

    def next_pool(self):
        self.n += 1
        self.heat = step_heat(self.rng, self.heat)
        self.heat_hist.append(self.heat)
        accel = self.heat - self.heat_hist[-market.ACCEL_LAG]
        p = Pool(self.rng, self.n, self.heat, accel)
        rr = self.rr
        v = market.telegram(p, rr, self.heat)
        self.pool = p
        self.thought = self.brain.think(p, self.heat_hist)
        # the telegram room this pool lives in, last 10 seconds
        self.tg = {"groups": rr.randint(3, 40) if v > 0.4 else rr.randint(0, 6),
                   "msgs": int(v * 180 + rr.uniform(0, 20)), "members": int(v * 60 + rr.uniform(0, 8)),
                   "links": int(v * 14 + rr.uniform(0, 3)), "emoji": clamp(0.2 + v * 0.6 + rr.gauss(0, 0.08)),
                   "vel": p.obs["tg velocity"]}
        for _ in range(1 + int(v * 4)):
            self.chat.append(("g/%03d" % rr.randint(1, 340), rr.choice(TG_LINES), v))
        for _ in range(rr.choice((0, 0, 1, 1, 2)) + (1 if v > VEL_HI else 0)):
            txt = rr.choice(TG_LINES)
            if rr.random() < 0.4:
                txt = txt + " " + p.name.lower()
            self.room.append({"who": rr.choice(USERS), "text": txt, "time": self.stamp()[-5:], "bee": False})
        if self.n - self.last_insight >= INSIGHT_EVERY:
            self.last_insight = self.n
            hi, hn = self.cells[(1, 1)], self.cells[(1, 0)]
            if hi[0] >= 5 and hn[0] >= 5:
                self.bee_says("what i keep seeing: loud room + old creator printed %d of %d (%.0f%%). "
                              "loud room + new creator %d of %d (%.0f%%). nobody told me to look at this."
                              % (hi[1], hi[0], 100 * hi[1] / hi[0], hn[1], hn[0], 100 * hn[1] / hn[0]), "insight")
        if self.n % SURFACE_EVERY == 0:
            self.update_surface()

    def bee_says(self, text, kind="info"):
        self.bee_queue.append((text, kind))

    @staticmethod
    def age_words(a):
        if a < 0.2:
            return "a few hours old"
        if a < 0.5:
            return "a couple of weeks old"
        return "%d months old" % int(1 + a * 8)

    def update_surface(self):
        for i, vel in enumerate((0.15, 0.45, 0.72, 0.92)):
            for j, age in enumerate((0.15, 0.4, 0.62, 0.85)):
                self.surface[i][j] = self.brain.probe(vel, age)

    def act(self):
        p, t = self.pool, self.thought
        self.counts[t["verdict"]] += 1
        hi = int(p.true["tg velocity"] > VEL_HI)
        old = int(p.true["creator age"] > AGE_OLD)
        c = self.cells[(hi, old)]
        c[0] += 1
        c[1] += 1 if p.final > 0 else 0
        if t["take"] and len(self.open) < MAX_OPEN:
            size = self.size_for(t["explore"])
            if size >= MIN_SIZE:
                self.cash -= size
                self.open.append(FixedPosition(self.rng, p, size, t["act"], t["explore"], self.n))
                self.say("%s %s %s mb %.2f tg %.2f" % (p.name, "exp" if t["explore"] else "pass", money(size),
                         t["lobes"]["mushroom"], p.obs["tg velocity"]), "tg" if p.obs["tg velocity"] > VEL_HI else "entry")
                if p.ct_lag and not t["explore"]:
                    self.catches.append((self.stamp(), p.id, p.name, p.obs["tg velocity"], p.true["creator age"],
                                         t["lobes"]["mushroom"], p.ct_lag, p.final))
                loud = p.obs["tg velocity"] > VEL_HI
                if loud:
                    self.bee_says("loud room on %s: %d msgs and %d new members in 10 s. creator is %s. "
                                  "mushroom %.2f. PASS, in with %s."
                                  % (p.name, self.tg["msgs"], self.tg["members"], self.age_words(p.true["creator age"]),
                                     t["lobes"]["mushroom"], money(size)), "pass")
                    if p.ct_lag and not t["explore"]:
                        self.bee_says("first ct post on %s just landed, %ds after i went in." % (p.name, p.ct_lag), "ct")
                elif not t["explore"]:
                    self.bee_says("%s: quiet room, creator %s. mushroom %.2f. PASS, %s."
                                  % (p.name, self.age_words(p.true["creator age"]), t["lobes"]["mushroom"], money(size)), "pass")
                return
        if p.obs["tg velocity"] > VEL_HI and p.true["creator age"] <= AGE_OLD and self.rr.random() < 0.5:
            n, w = self.cells[(1, 0)]
            self.bee_says("%s is loud but the creator is %s. %d rooms like this so far, %.0f%% printed. skip."
                          % (p.name, self.age_words(p.true["creator age"]), n, 100 * w / max(1, n)), "skip")
        ghost_won = p.final > 0
        self.brain.learn(t["act"], ghost_won, GHOST_LR)
        self.brain.memory.append((t["act"], 1 if ghost_won else 0))


__all__ = ["Engine", "GrokEngine", "TelegramEngine", "Position", "FixedPosition", "run", "parse_seeds",
           "money", "START_CASH", "POOLS_PER_DAY", "FEE", "FEATS"]
