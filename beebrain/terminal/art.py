"""what the terminal draws: the bee brain cells, the rotating 3d brain, the lab spike sims.
display only. nothing here feeds back into the model."""
import math
import random
from collections import deque

from ..brain import FEATS, N_KC
from ..market import VEL_HI
from .canvas import (BOLD, BONE, DIM, ESC, GREEN, PINK, PINK_D, PINK_H, PINK_X, line_pts)


class BrainArt:
    """cells laid out on a bee brain, lit by what each lobe is actually doing."""

    REGIONS = {
        # name: list of (dx, dy, rx, ry) ellipses relative to centre
        "optic": [(-28, 1, 8, 8), (28, 1, 8, 8)],
        "mushroom": [(-17, -7, 4, 2), (-6, -8, 3, 2), (6, -8, 3, 2), (17, -7, 4, 2)],
        "central": [(0, -1, 8, 2)],
        "antennal": [(-8, 6, 5, 2), (8, 6, 5, 2)],
        "motor": [(0, 10, 6, 2)],
    }
    TRACTS = [
        ("antennal", "mushroom", (-9, 4), (-16, -5)), ("antennal", "mushroom", (9, 4), (16, -5)),
        ("optic", "mushroom", (-21, -3), (-20, -6)), ("optic", "mushroom", (21, -3), (20, -6)),
        ("optic", "central", (-19, 1), (-9, 0)), ("optic", "central", (19, 1), (9, 0)),
        ("mushroom", "central", (-14, -5), (-6, -2)), ("mushroom", "central", (14, -5), (6, -2)),
        ("mushroom", "central", (-5, -6), (-2, -2)), ("mushroom", "central", (5, -6), (2, -2)),
        ("central", "motor", (0, 1), (0, 8)), ("antennal", "motor", (-5, 7), (-3, 9)),
        ("antennal", "motor", (5, 7), (3, 9)),
    ]

    def __init__(self, rng):
        self.rng = rng
        self.cells = {}
        for name, ells in self.REGIONS.items():
            cells = []
            for (cx, cy, rx, ry) in ells:
                for dy in range(-ry, ry + 1):
                    for dx in range(-rx, rx + 1):
                        if (dx / (rx + .5)) ** 2 + (dy / (ry + .5)) ** 2 <= 1:
                            cells.append([cx + dx, cy + dy, 0.0])
            self.cells[name] = cells
        # lobe outlines, so the shape of the brain reads at a glance
        self.rims = {}
        for name, ells in self.REGIONS.items():
            pts = set()
            for (cx, cy, rx, ry) in ells:
                for k in range(240):
                    t = k / 240 * 2 * math.pi
                    pts.add((cx + round((rx + 1.6) * math.cos(t)), cy + round((ry + 1.0) * math.sin(t))))
            inside = {(c[0], c[1]) for c in self.cells[name]}
            self.rims[name] = sorted(pts - inside)
        self.glow = {name: 0.0 for name in self.REGIONS}
        self.tracts = [(a, b, line_pts(p, q)) for a, b, p, q in self.TRACTS]
        self.pulses = []           # [pts, i, col]
        self.seg_col = DIM
        self.bump = 0.5
        self.fires = 0

    def total_cells(self):
        return sum(len(c) for c in self.cells.values())

    def excite(self, name, fn):
        self.glow[name] = 1.0
        for i, c in enumerate(self.cells[name]):
            c[2] = max(c[2], fn(i, c))

    def fire(self, src):
        for a, b, pts in self.tracts:
            if a == src:
                for k in range(3):
                    self.pulses.append([pts, -k * 2, BONE])
                    self.fires += 1

    def step(self):
        for name, cells in self.cells.items():
            self.glow[name] *= 0.97
            # the mushroom bodies stay dark so the sparse 5% code stands out
            floor = (0.1 + 0.08 * self.glow[name]) if name == "mushroom" else (0.14 + 0.25 * self.glow[name])
            for c in cells:
                c[2] = max(floor, c[2] * 0.88)
                if self.rng.random() < 0.02:          # spontaneous firing, the brain is never silent
                    c[2] = max(c[2], self.rng.uniform(0.35, 0.7))
        keep = []
        for p in self.pulses:
            p[1] += 1
            if p[1] < len(p[0]):
                keep.append(p)
        self.pulses = keep

    def draw(self, cv, ox, oy):
        for _, _, pts in self.tracts:
            for (x, y) in pts:
                cv.put(ox + x, oy + y, "·", PINK_D)
        for name, pts in self.rims.items():
            g = self.glow[name]
            col = PINK_H if g > 0.7 else (PINK if g > 0.35 else PINK_D)
            for (x, y) in pts:
                cv.put(ox + x, oy + y, "·", col)
        for name, cells in self.cells.items():
            for (x, y, a) in cells:
                if a > 0.85:
                    ch, col = "●", BOLD + PINK_H
                elif a > 0.6:
                    ch, col = "●", PINK
                elif a > 0.4:
                    ch, col = "•", PINK
                elif a > 0.25:
                    ch, col = "•", PINK_D
                else:
                    ch, col = "∙", PINK_X
                if name == "motor" and a > 0.45:
                    col = self.seg_col
                cv.put(ox + x, oy + y, ch, col)
        for pts, i, col in self.pulses:
            if 0 <= i < len(pts):
                x, y = pts[i]
                cv.put(ox + x, oy + y, "◆", col)


class LabSim:
    """the brain simulations for the telegram lab: spiking glomeruli, a kenyon layer, output neurons."""

    def __init__(self, seed):
        self.rng = random.Random(seed + 555)
        self.v = [0.0] * 9                       # membrane potentials, 8 on-chain + telegram
        self.spk = [deque([0] * 90, maxlen=90) for _ in range(9)]
        self.trace = deque([0.0] * 170, maxlen=170)
        self.kc_show = [self.rng.randrange(N_KC) for _ in range(8)]
        self.kc_spk = [deque([0] * 90, maxlen=90) for _ in range(8 + 4)]
        self.mbon = [deque([0] * 90, maxlen=90) for _ in range(2)]
        self.kc_glow = [0.0] * 1000
        self.kc_map = [self.rng.randrange(N_KC) for _ in range(1000)]
        self.reward = 0.0
        self.reward_col = GREEN
        self.curve_old = deque(maxlen=120)
        self.curve_new = deque(maxlen=120)
        self.spikes = 0

    def step(self, e, stage):
        p = e.pool
        feats = [p.obs[f] for f in FEATS] + [p.obs["tg velocity"]] if p else [0.2] * 9
        for i in range(8):                       # on-chain glomeruli: rate coded spikes
            fired = 1 if self.rng.random() < 0.04 + 0.30 * feats[i] ** 1.5 else 0
            self.spikes += fired
            self.spk[i].append(fired)
        # glomerulus 9 is a leaky integrate and fire neuron driven by telegram velocity
        drive = 0.25 + 1.05 * feats[8] + self.rng.gauss(0, 0.10)
        self.v[8] += (drive - self.v[8]) * 0.22 + self.rng.gauss(0, 0.04)
        fired = 0
        if self.v[8] > 1.0:
            fired = 1
            self.spikes += 1
            self.v[8] = -0.15
        self.spk[8].append(fired)
        self.trace.append(1.25 if fired else self.v[8])
        act = e.thought["act"] if e.thought else frozenset()
        firing = stage == "mushroom"
        for j, k in enumerate(self.kc_show):
            self.kc_spk[j].append(1 if (firing and k in act) or self.rng.random() < 0.01 else 0)
        # four cross-modal cells: loud and old creator, loud and new, quiet and old, quiet and new
        if p:
            loud = p.obs["tg velocity"] > VEL_HI
            old = p.obs["creator age"] > 0.5
            for j, (lo, o) in enumerate(((1, 1), (1, 0), (0, 1), (0, 0))):
                on = firing and loud == bool(lo) and old == bool(o)
                self.kc_spk[8 + j].append(1 if on else 0)
        mb = e.thought["lobes"]["mushroom"] if e.thought else 0.5
        out_stage = stage in ("central", "motor")
        self.mbon[0].append(1 if out_stage and self.rng.random() < mb * 0.8 else 0)
        self.mbon[1].append(1 if out_stage and self.rng.random() < (1 - mb) * 0.8 else 0)
        for i in range(1000):
            self.kc_glow[i] *= 0.95
            if firing and self.kc_map[i] in act:
                self.kc_glow[i] = 1.0
            elif self.rng.random() < 0.002:
                self.kc_glow[i] = max(self.kc_glow[i], 0.4)
        self.reward *= 0.9


class Brain3D:
    """a rotating 3d honeybee brain in pure python, drawn with half blocks for double vertical resolution.
    lobes follow the same layout as the article renders; the telegram glomerulus is its own blue body."""

    PAL = {
        "optic": [60, 61, 62, 104, 147],
        "mushroom": [89, 125, 162, 205, 218],
        "central": [60, 97, 140, 183, 225],
        "antennal": [24, 25, 61, 69, 111],
        "tg": [24, 31, 38, 45, 159],
        "motor": [52, 88, 124, 160, 210],
        "haze": [236, 237, 237, 238, 239],
    }

    def __init__(self, seed):
        R = random.Random(seed + 77)
        P = []

        def ell(n, c, r, lobe, shell=0.0, tag=0):
            for _ in range(n):
                while True:
                    v = [R.gauss(0, 1) for _ in range(3)]
                    m = math.sqrt(sum(a * a for a in v)) or 1
                    rad = (1 - shell * R.random()) if shell else R.random() ** (1 / 3)
                    p = [c[i] + v[i] / m * rad * r[i] for i in range(3)]
                    break
                P.append([p[0], p[1], p[2], lobe, tag])

        def cup(n, c, rad):
            for _ in range(n):
                v = [R.gauss(0, 1) for _ in range(3)]
                m = math.sqrt(sum(a * a for a in v)) or 1
                v = [a / m for a in v]
                v[1] = -abs(v[1]) * 0.8 + 0.15
                k = (1 - 0.28 * R.random()) * rad
                P.append([c[0] + v[0] * k, c[1] + v[1] * k, c[2] + v[2] * k, "mushroom", 0])

        def tube(n, pts, rr, lobe):
            for _ in range(n):
                i = R.randrange(len(pts) - 1)
                u = R.random()
                a, b = pts[i], pts[i + 1]
                P.append([a[0] + (b[0] - a[0]) * u + R.gauss(0, rr), a[1] + (b[1] - a[1]) * u + R.gauss(0, rr),
                          a[2] + (b[2] - a[2]) * u + R.gauss(0, rr), lobe, 1])

        for sx in (-1, 1):
            ell(900, (0.80 * sx, 0.0, 0.0), (0.17, 0.46, 0.30), "optic", shell=0.45)
            ell(420, (0.56 * sx, -0.02, 0.02), (0.10, 0.30, 0.20), "optic")
            ell(260, (1.00 * sx, 0.0, -0.02), (0.05, 0.46, 0.30), "optic", shell=0.25)
            for cx in (0.13, 0.33):
                cup(320, (cx * sx, 0.36, -0.06), 0.105)
            tube(220, [(0.23 * sx, 0.28, -0.04), (0.22 * sx, 0.16, 0.06), (0.20 * sx, 0.08, 0.16)], 0.025, "mushroom")
            tube(140, [(0.20 * sx, 0.08, 0.16), (0.24 * sx, 0.22, 0.24), (0.26 * sx, 0.34, 0.26)], 0.03, "mushroom")
            tube(140, [(0.20 * sx, 0.08, 0.16), (0.10 * sx, 0.05, 0.20), (0.02 * sx, 0.05, 0.21)], 0.028, "mushroom")
            ell(300, (0.15 * sx, -0.20, 0.26), (0.10, 0.10, 0.10), "antennal", shell=0.3)
        ell(160, (0.0, -0.24, 0.34), (0.06, 0.06, 0.06), "tg")         # the ninth glomerulus
        ell(360, (0, 0.03, 0.0), (0.17, 0.055, 0.05), "central")
        for i in range(90):
            xx = -0.22 + 0.44 * i / 89
            P.append([xx, 0.14 - 0.9 * xx * xx, -0.12, "central", 1])
        ell(380, (0, -0.40, 0.08), (0.20, 0.10, 0.13), "motor")
        ell(900, (0, 0.02, 0.02), (0.52, 0.44, 0.34), "haze")
        self.P = P
        self.act = [0.0] * len(P)
        self.base = [0.28 + 0.12 * R.random() if p[3] != "haze" else 0.12 for p in P]
        self.idx = {}
        for i, p in enumerate(P):
            self.idx.setdefault(p[3], []).append(i)
        self.glow = {k: 0.0 for k in self.PAL}
        self.R = R
        self.tract = [(0.0, -0.24, 0.34), (0.08, -0.05, 0.25), (0.15, 0.20, 0.0), (0.23, 0.36, -0.06)]
        self.pulses = []
        self.motor_col = None

    def excite(self, lobe, frac=1.0, level=1.0):
        self.glow[lobe] = 1.0
        for i in self.idx.get(lobe, []):
            if frac >= 1 or self.R.random() < frac:
                self.act[i] = max(self.act[i], level)

    def step(self):
        for k in self.glow:
            self.glow[k] *= 0.94
        for i in range(len(self.act)):
            self.act[i] *= 0.9
        for _ in range(40):
            i = self.R.randrange(len(self.P))
            self.act[i] = max(self.act[i], 0.45)
        keep = []
        for p in self.pulses:
            p[0] += 0.06
            if p[0] < 1:
                keep.append(p)
        self.pulses = keep

    def draw(self, cv, x, y, w, h, yaw, pitch=0.18):
        gw, gh = w, h * 2
        best = [[(-9, None)] * gw for _ in range(gh)]
        cy_, sy_ = math.cos(yaw), math.sin(yaw)
        cp, sp = math.cos(pitch), math.sin(pitch)
        sc = min(gw / 2.35, gh / 1.05)
        for i, (px, py, pz, lobe, tag) in enumerate(self.P):
            X = px * cy_ + pz * sy_
            Z = -px * sy_ + pz * cy_
            Y = py * cp - Z * sp
            Z = py * sp + Z * cp
            f = 3.2 / (3.2 - Z)
            u = int(gw / 2 + X * sc * f)
            v = int(gh / 2 - Y * sc * f)
            if 0 <= u < gw and 0 <= v < gh:
                bright = (self.base[i] + self.act[i] + 0.25 * self.glow[lobe]) * (0.75 + 0.35 * Z)
                if bright > best[v][u][0]:
                    best[v][u] = (bright, lobe)
        for (t, col) in self.pulses:
            a = self.tract
            seg = min(len(a) - 2, int(t * (len(a) - 1)))
            u0 = t * (len(a) - 1) - seg
            px = a[seg][0] + (a[seg + 1][0] - a[seg][0]) * u0
            py = a[seg][1] + (a[seg + 1][1] - a[seg][1]) * u0
            pz = a[seg][2] + (a[seg + 1][2] - a[seg][2]) * u0
            for sx in (1, -1):
                X = sx * px * cy_ + pz * sy_
                Z = -sx * px * sy_ + pz * cy_
                Y = py * cp - Z * sp
                f = 3.2 / (3.2 - (py * sp + Z * cp))
                u = int(gw / 2 + X * sc * f)
                v = int(gh / 2 - Y * sc * f)
                if 0 <= u < gw and 0 <= v < gh:
                    best[v][u] = (9, "pulse")

        def code(cell):
            b, lobe = cell
            if lobe is None:
                return 235
            if lobe == "pulse":
                return 231
            if lobe == "motor" and self.motor_col is not None and self.glow["motor"] > 0.3:
                return self.motor_col
            pal = self.PAL[lobe]
            if b > 1.05 and lobe in ("mushroom", "tg"):
                return 231
            return pal[max(0, min(4, int(b * 4.2)))]

        for r in range(h):
            for c in range(gw):
                top, bot = code(best[2 * r][c]), code(best[2 * r + 1][c])
                if top == 235 and bot == 235:
                    continue
                cv.put(x + c, y + r, "▀", ESC + "38;5;%dm" % top + ESC + "48;5;%dm" % bot)
