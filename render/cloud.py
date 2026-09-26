"""
beebrain 3d: a point cloud honeybee brain with lobes that fire.
used by video.py, stills.py and bee.py. needs numpy and scipy.

geometry is schematic, laid out from the published bee brain anatomy:
optic lobes (medulla + lobula) on the sides, mushroom bodies with two cup shaped
calyces per side and their stalks, central complex (fan shaped body + bridge),
antennal lobes with glomeruli, subesophageal ganglion below.

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import math
import numpy as np
from scipy.ndimage import gaussian_filter

RNG = np.random.default_rng(7)

COL = {
    "optic":    np.array([157, 124, 255], float),
    "mushroom": np.array([255, 79, 163], float),
    "central":  np.array([196, 168, 255], float),
    "antennal": np.array([143, 132, 255], float),
    "motor":    np.array([255, 84, 104], float),
    "haze":     np.array([150, 60, 110], float),
    "tract":    np.array([176, 48, 111], float),
    "shell":    np.array([230, 220, 200], float),
    "eye":      np.array([255, 176, 74], float),
    "antenna":  np.array([255, 196, 110], float),
}


def ellipsoid(n, c, r, shell=0.0):
    """n points inside an ellipsoid; shell>0 pushes them toward the surface"""
    v = RNG.normal(size=(n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    rad = RNG.random(n) ** (1 / 3)
    if shell:
        rad = 1 - shell * RNG.random(n)
    return np.array(c) + v * rad[:, None] * np.array(r)


def cup(n, c, radius, depth=0.8):
    """calyx: a hemispherical cup opening upward, thick rim"""
    v = RNG.normal(size=(n, 3))
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    v[:, 1] = -np.abs(v[:, 1]) * depth + 0.15
    rad = 1 - 0.28 * RNG.random(n)
    return np.array(c) + v * rad[:, None] * radius


def tube(n, pts, radius):
    pts = np.array(pts, float)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    t = RNG.random(n) * cum[-1]
    idx = np.clip(np.searchsorted(cum, t) - 1, 0, len(seg) - 1)
    f = ((t - cum[idx]) / seg[idx])[:, None]
    base = pts[idx] + (pts[idx + 1] - pts[idx]) * f
    return base + RNG.normal(scale=radius, size=(n, 3))


def bezier(p0, p1, p2, p3, k=60):
    t = np.linspace(0, 1, k)[:, None]
    return ((1 - t) ** 3) * p0 + 3 * ((1 - t) ** 2) * t * p1 + 3 * (1 - t) * t * t * p2 + t ** 3 * p3


class Brain:
    def __init__(self, head=False):
        P, L, S = [], [], []          # positions, lobe index, sub id (glomerulus / side)
        self.names = ["optic", "mushroom", "central", "antennal", "motor", "haze", "shell", "eye", "antenna"]
        def add(pts, lobe, sub=0):
            P.append(pts); L.append(np.full(len(pts), self.names.index(lobe))); S.append(np.full(len(pts), sub) if np.isscalar(sub) else sub)

        for sx in (-1, 1):
            # optic lobes: medulla (outer) and lobula (inner), bent like kidneys
            med = ellipsoid(9000, (0.80 * sx, 0.0, 0.0), (0.17, 0.46, 0.30), shell=0.45)
            med[:, 0] += sx * 0.10 * (med[:, 1] / 0.46) ** 2
            add(med, "optic", 0)
            lob = ellipsoid(4200, (0.56 * sx, -0.02, 0.02), (0.10, 0.30, 0.20))
            add(lob, "optic", 1)
            lam = ellipsoid(2600, (1.00 * sx, 0.0, -0.02), (0.05, 0.46, 0.30), shell=0.25)
            lam[:, 0] += sx * 0.12 * (lam[:, 1] / 0.46) ** 2
            add(lam, "optic", 2)
            # mushroom bodies: two calyces per side, stalk, vertical + medial lobes
            for cx in (0.13, 0.33):
                add(cup(2600, (cx * sx, 0.36, -0.06), 0.105), "mushroom", 0)
            add(tube(1800, [(0.23 * sx, 0.28, -0.04), (0.22 * sx, 0.16, 0.06), (0.20 * sx, 0.08, 0.16)], 0.025), "mushroom", 1)
            add(tube(1100, [(0.20 * sx, 0.08, 0.16), (0.24 * sx, 0.22, 0.24), (0.26 * sx, 0.34, 0.26)], 0.03), "mushroom", 1)
            add(tube(1100, [(0.20 * sx, 0.08, 0.16), (0.10 * sx, 0.05, 0.20), (0.02 * sx, 0.05, 0.21)], 0.028), "mushroom", 1)
            # antennal lobes: glomeruli on a shell
            centers = RNG.normal(size=(40, 3)); centers /= np.linalg.norm(centers, axis=1, keepdims=True)
            g = []
            gid = []
            for i, cc in enumerate(centers):
                pts = (0.15 * sx, -0.20, 0.26) + cc * 0.10 + RNG.normal(scale=0.012, size=(70, 3))
                g.append(pts); gid.append(np.full(70, i))
            add(np.vstack(g), "antennal", np.concatenate(gid))
        # central complex: fan shaped body, ellipsoid body, protocerebral bridge
        fb = ellipsoid(3000, (0, 0.03, 0.0), (0.17, 0.055, 0.05))
        add(fb, "central", 0)
        add(ellipsoid(900, (0, -0.03, 0.03), (0.07, 0.03, 0.03)), "central", 1)
        xs = np.linspace(-0.22, 0.22, 900)
        pb = np.stack([xs, 0.14 - 0.9 * xs ** 2, np.full_like(xs, -0.12)], 1) + RNG.normal(scale=0.01, size=(900, 3))
        add(pb, "central", 2)
        # subesophageal ganglion
        add(ellipsoid(3200, (0, -0.40, 0.08), (0.20, 0.10, 0.13)), "motor", 0)
        # central brain haze so it reads as one organ
        haze = ellipsoid(9000, (0, 0.02, 0.02), (0.52, 0.44, 0.34))
        add(haze, "haze", 0)

        if head:
            # the bee around the brain: head capsule, compound eyes, ocelli, antennae, mandibles
            sh = ellipsoid(7000, (0, -0.10, 0.10), (1.30, 1.12, 0.62), shell=0.04)
            sh[:, 0] *= 1 - 0.18 * np.clip(-(sh[:, 1] + 0.1) / 1.1, 0, 1)      # narrower toward the mouth
            add(sh, "shell", 0)
            # fuzz: short hairs standing off the upper head
            fz = ellipsoid(5000, (0, -0.10, 0.10), (1.30, 1.12, 0.62), shell=0.02)
            fz = fz[fz[:, 1] > -0.2]
            nrm = (fz - np.array((0, -0.10, 0.10))) / np.array((1.30, 1.12, 0.62)) ** 2
            nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
            fz = fz + nrm * RNG.random((len(fz), 1)) * 0.16
            add(fz, "shell", 2)
            for sx in (-1, 1):
                eye = ellipsoid(12000, (1.10 * sx, 0.12, 0.28), (0.30, 0.78, 0.40), shell=0.06)
                eye[:, 0] -= sx * 0.10 * ((eye[:, 1] - 0.12) / 0.78) ** 2
                add(eye, "eye", 0)
                scape = tube(1400, [(0.16 * sx, -0.02, 0.66), (0.24 * sx, 0.40, 0.92), (0.30 * sx, 0.70, 1.00)], 0.03)
                add(scape, "antenna", 0)
                flag = []
                pts = bezier(np.array((0.30 * sx, 0.70, 1.00)), np.array((0.50 * sx, 1.05, 0.95)),
                             np.array((0.72 * sx, 1.30, 0.80)), np.array((0.95 * sx, 1.42, 0.62)), 11)
                for c in pts:
                    flag.append(np.array(c) + RNG.normal(scale=0.034, size=(160, 3)))
                add(np.vstack(flag), "antenna", 1)
                mand = tube(1200, [(0.34 * sx, -0.92, 0.50), (0.22 * sx, -1.14, 0.58), (0.06 * sx, -1.20, 0.60)], 0.035)
                add(mand, "shell", 1)
            for c in ((0, 0.86, 0.36), (-0.2, 0.78, 0.40), (0.2, 0.78, 0.40)):
                add(ellipsoid(260, c, (0.05, 0.05, 0.05)), "eye", 1)
        self.P = np.vstack(P)
        self.L = np.concatenate(L)
        self.S = np.concatenate(S)
        lb = {5: 0.06, 6: 0.17, 7: 0.42, 8: 0.75}
        self.base = np.array([lb.get(int(l_), 0.30) for l_ in self.L]) * (0.6 + 0.4 * RNG.random(len(self.P)))
        self.spark = np.where(RNG.random(len(self.P)) < 0.08, 2.6, 1.0)
        self.col = np.stack([COL[self.names[i]] for i in self.L]) / 255.0
        self.act = np.zeros(len(self.P))
        self.tint = np.zeros((len(self.P), 3))   # motor verdict colour overlay
        self.tint_amt = np.zeros(len(self.P))

        # tracts used by pulses
        T = {}
        for sx, nm in ((-1, "L"), (1, "R")):
            T["al_mb" + nm] = bezier(np.array((0.15 * sx, -0.14, 0.24)), np.array((0.12 * sx, 0.10, 0.02)),
                                     np.array((0.18 * sx, 0.30, -0.12)), np.array((0.23 * sx, 0.36, -0.06)))
            T["ol_mb" + nm] = bezier(np.array((0.58 * sx, 0.10, 0.0)), np.array((0.46 * sx, 0.28, -0.05)),
                                     np.array((0.38 * sx, 0.40, -0.08)), np.array((0.33 * sx, 0.38, -0.06)))
            T["ol_cx" + nm] = bezier(np.array((0.56 * sx, -0.02, 0.0)), np.array((0.40 * sx, 0.0, 0.0)),
                                     np.array((0.25 * sx, 0.03, 0.0)), np.array((0.15 * sx, 0.03, 0.0)))
            T["mb_cx" + nm] = bezier(np.array((0.20 * sx, 0.08, 0.16)), np.array((0.14 * sx, 0.06, 0.10)),
                                     np.array((0.08 * sx, 0.04, 0.04)), np.array((0.04 * sx, 0.03, 0.0)))
            T["reward_al" + nm] = bezier(np.array((0.0, -0.36, 0.08)), np.array((0.05 * sx, -0.30, 0.16)),
                                         np.array((0.12 * sx, -0.26, 0.24)), np.array((0.15 * sx, -0.20, 0.26)))
            T["reward_mb" + nm] = bezier(np.array((0.0, -0.36, 0.08)), np.array((0.02 * sx, -0.05, -0.10)),
                                         np.array((0.15 * sx, 0.25, -0.14)), np.array((0.23 * sx, 0.36, -0.06)))
        T["cx_seg"] = bezier(np.array((0.0, 0.0, 0.03)), np.array((0.0, -0.12, 0.05)),
                             np.array((0.0, -0.24, 0.07)), np.array((0.0, -0.34, 0.08)))
        self.tracts = T
        tp = np.vstack(list(T.values()))
        self.tract_pts = tp

    # ---------------------------------------------------------------- activity
    def mask(self, lobe):
        return self.L == self.names.index(lobe)

    def decay(self, k=0.90):
        self.act *= k
        self.tint_amt *= 0.93
        # spontaneous firing, the brain is never silent
        n = len(self.P)
        idx = RNG.integers(0, n, size=n // 180)
        self.act[idx] = np.maximum(self.act[idx], RNG.uniform(0.25, 0.6, size=len(idx)))

    def excite(self, lobe, values):
        m = self.mask(lobe)
        self.act[m] = np.maximum(self.act[m], values)


# ------------------------------------------------------------------- render
def rot(yaw, pitch):
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return Rx @ Ry


def project(P, W, H, yaw, pitch, dist, scale, cx=None, cy=None):
    Q = P @ rot(yaw, pitch).T
    z = Q[:, 2] + dist
    f = scale / z
    x = (cx if cx is not None else W / 2) + Q[:, 0] * f
    y = (cy if cy is not None else H / 2) - Q[:, 1] * f
    return x, y, z, f


def splat(W, H, x, y, rgb, w):
    img = np.zeros((H, W, 3), np.float32)
    xi = np.round(x).astype(int); yi = np.round(y).astype(int)
    ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
    xi, yi, rgb, w = xi[ok], yi[ok], rgb[ok], w[ok]
    for c in range(3):
        np.add.at(img[:, :, c], (yi, xi), rgb[:, c] * w)
    return img


def render(brain, W, H, yaw, pitch, dist=3.2, scale=None, pulses=(), extra=None, cx=None, cy=None, exposure=1.0):
    scale = scale or H * 2.05
    x, y, z, f = project(brain.P, W, H, yaw, pitch, dist, scale, cx, cy)
    depth = np.clip((dist + 0.6 - z) / 1.2, 0.35, 1.0)
    a = brain.base + brain.act
    col = brain.col * (1 - brain.tint_amt[:, None]) + brain.tint * brain.tint_amt[:, None]
    # hot cells go toward white
    hot = np.clip(brain.act - 0.6, 0, 1)[:, None]
    col = col * (1 - hot * 0.7) + hot * 0.7
    w = a * depth * brain.spark * 0.95 * (1 + 3.5 * hot[:, 0])
    img = splat(W, H, x, y, col, w)
    # tracts, faint
    tx, ty, tz, _ = project(brain.tract_pts, W, H, yaw, pitch, dist, scale, cx, cy)
    img += splat(W, H, tx, ty, np.tile(COL["tract"] / 255, (len(tx), 1)), np.full(len(tx), 0.35))
    # pulses: bright heads with short trails
    for pts, t, color in pulses:
        k = len(pts)
        i = t * (k - 1)
        seg = []
        for j in range(8):
            u = max(0.0, i - j * 1.2)
            a0 = int(u); b0 = min(k - 1, a0 + 1); fr = u - a0
            seg.append(pts[a0] * (1 - fr) + pts[b0] * fr)
        seg = np.array(seg)
        px, py, pz, _ = project(seg, W, H, yaw, pitch, dist, scale, cx, cy)
        wts = np.linspace(6.0, 0.8, len(seg))
        img += splat(W, H, px, py, np.tile(np.array(color) / 255, (len(seg), 1)), wts)
    if extra is not None:
        img += extra
    glow1 = gaussian_filter(img, sigma=(2.2, 2.2, 0))
    glow2 = gaussian_filter(img, sigma=(9, 9, 0))
    out = img * 1.4 + glow1 * 2.0 + glow2 * 2.2
    out = 1 - np.exp(-out * exposure * 1.6)     # soft tone map
    return (np.clip(out, 0, 1) * 255).astype(np.uint8), (x, y)
