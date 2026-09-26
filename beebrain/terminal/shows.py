"""a show drives one pool through the brain over a few frames so you can watch it.
the engine does the same three calls as a headless run, only spread over frames."""
import math
import random
from collections import deque

from ..brain import FEATS, N_KC, clamp
from ..engine import Engine, GrokEngine, TelegramEngine, GROK_START, TG_START, money
from ..market import VEL_HI
from .art import Brain3D, BrainArt, LabSim
from .canvas import BONE, GREEN, RED


class Show:
    """drives one pool through the brain over a few frames so you can watch it."""

    def __init__(self, seed, speed):
        self.e = Engine(seed)
        self.art = BrainArt(random.Random(seed + 1))
        self.cycle = max(6, int(round(20 / max(0.2, speed))))
        self.f = 0
        self.stage = "idle"
        self.frame = 0
        self.waggle_t = 0.0
        self.trail = deque(maxlen=80)
        self.live = None
        self.post = 1

    def step(self):
        e, art = self.e, self.art
        k = self.f % self.cycle
        c = self.cycle
        if k == 0:
            e.next_pool()
            e.tick_positions()
            o = e.pool.obs
            self.stage = "antennal"
            # glomeruli: each feature lights its own slice of the antennal lobes
            n = len(art.cells["antennal"])
            art.excite("antennal", lambda i, cc: o[FEATS[i * 8 // n]] * (0.6 + 0.4 * e.thought["lobes"]["antennal"]))
            art.fire("antennal")
        elif k == int(c * 0.22):
            self.stage = "optic"
            hist = list(e.heat_hist)
            art.excite("optic", lambda i, cc: hist[int(((cc[0] + 37) % 18) / 18 * 59)] * 1.1
                       if abs(cc[1] - 1) <= 8 else 0)
            art.fire("optic")
        elif k == int(c * 0.40):
            self.stage = "mushroom"
            act = e.thought["act"]
            # every drawn cell is one real kenyon cell. only the sparse 5% light.
            art.excite("mushroom", lambda i, cc: 1.0 if (i * 37) % N_KC in act or
                       ((i * 37 + 1) % N_KC) in act else 0.05)
            art.fire("mushroom")
        elif k == int(c * 0.60):
            self.stage = "central"
            art.bump = e.thought["comb"]
            xs = [cc[0] for cc in art.cells["central"]]
            lo, hi = min(xs), max(xs)
            pos = lo + (hi - lo) * clamp((e.thought["comb"] - 0.3) / 0.5)
            art.excite("central", lambda i, cc: math.exp(-((cc[0] - pos) ** 2) / 6.0))
            art.fire("central")
        elif k == int(c * 0.78):
            self.stage = "motor"
            v = e.thought["verdict"]
            art.seg_col = GREEN if v == "PASS" else (RED if v == "SKIP" else BONE)
            art.excite("motor", lambda i, cc: 1.0)
            e.act()
        art.step()
        self.f += 1
        self.frame += 1
        # waggle: run length follows combined score, the wiggle follows lobe disagreement
        self.waggle_t += 0.16
        self.trail.append(self.waggle_xy(self.waggle_t))

    def waggle_xy(self, t):
        th = self.e.thought
        comb = th["comb"] if th else 0.5
        cons = th["consensus"] if th else 0.5
        s = t % (2 * math.pi)
        run = 0.35 + 0.65 * clamp((comb - 0.3) / 0.5)
        rp = math.pi * 0.8
        if s < rp:                               # straight waggle run down the middle
            u = s / rp
            y = run * (1 - 2 * u)
            x = 0.22 * (1.1 - cons) * math.sin(u * 26)
        else:                                    # return loop, alternating sides
            u = (s - rp) / (2 * math.pi - rp)
            side = -1 if int(t / (2 * math.pi)) % 2 else 1
            ang = math.pi * u
            x = side * 0.9 * math.sin(ang)
            y = -run + 2 * run * u
        return x, y


class Show2(Show):
    def __init__(self, seed, speed, start=GROK_START):
        super().__init__(seed, speed)
        self.e = GrokEngine(seed, start)
        self.post = 2
        self.cycle = max(8, int(round(28 / max(0.2, speed))))
        self.gseen = None
        self.gt0 = 0

    def step(self):
        if self.f % self.cycle == 0:
            self.e.reread()
        super().step()
        if self.e.grok is not self.gseen:
            self.gseen = self.e.grok
            self.gt0 = self.frame


class Show3(Show):
    def __init__(self, seed, speed, start=TG_START):
        super().__init__(seed, speed)
        self.e = TelegramEngine(seed, start)
        self.post = 3
        self.cycle = max(6, int(round(18 / max(0.2, speed))))
        self.typing = None          # (text, kind, frames left)
        self.closed_seen = 0

    def step(self):
        super().step()
        e = self.e
        # every close becomes a message too
        while self.closed_seen < len(e.closed):
            name, pnl, fin, mn, exp = e.closed[self.closed_seen]
            self.closed_seen += 1
            e.bee_says("%s closed %+.0f%%, %s%s. %s sent back to memory."
                       % (name, fin * 100, "+" if pnl >= 0 else "-", money(abs(pnl)),
                          "sugar" if pnl > 0 else "punishment"), "win" if pnl > 0 else "loss")
        if self.typing is None and e.bee_queue:
            text, kind = e.bee_queue.popleft()
            self.typing = [text, kind, 6 + min(14, len(text) // 12)]
        elif self.typing is not None:
            self.typing[2] -= 1
            if self.typing[2] <= 0:
                e.room.append({"who": "beebrain", "text": self.typing[0], "time": e.stamp()[-5:],
                               "bee": True, "kind": self.typing[1]})
                self.typing = None
        while len(e.bee_queue) > 6:          # never fall far behind the market
            e.bee_queue.popleft()


class Show3b(Show3):
    def __init__(self, seed, speed, start=TG_START):
        super().__init__(seed, speed, start)
        self.lab = LabSim(seed)
        self.closed_seen_lab = 0
        self.big = Brain3D(seed)
        self.last_stage = None

    def step(self):
        super().step()
        e = self.e
        self.lab.step(e, self.stage)
        big = self.big
        if self.stage != self.last_stage and e.pool:
            self.last_stage = self.stage
            vel = e.pool.obs["tg velocity"]
            if self.stage == "antennal":
                big.excite("antennal", 0.6, 0.8)
                big.excite("tg", 1.0, 0.4 + 0.8 * vel)
                if vel > VEL_HI:
                    big.pulses += [[0.0, 45], [0.15, 45], [0.3, 45]]
            elif self.stage == "optic":
                big.excite("optic", 0.35, 0.8)
            elif self.stage == "mushroom":
                big.excite("mushroom", 0.07, 1.25)
            elif self.stage == "central":
                big.excite("central", 0.5, 1.0)
            elif self.stage == "motor":
                v = e.thought["verdict"]
                big.motor_col = 42 if v == "PASS" else (196 if v == "SKIP" else 214)
                big.excite("motor", 1.0, 0.9)
        big.step()
        while self.closed_seen_lab < len(e.closed):
            pnl = e.closed[self.closed_seen_lab][1]
            self.closed_seen_lab += 1
            self.lab.reward = 1.0
            self.lab.reward_col = GREEN if pnl > 0 else RED
        if e.n % 25 == 0 and (not self.lab.curve_old or self.lab.curve_old[-1][0] != e.n):
            self.lab.curve_old.append((e.n, e.surface[3][3]))
            self.lab.curve_new.append((e.n, e.surface[3][0]))
