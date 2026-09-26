"""a whole honeybee as a particle cloud, brain glowing inside the head.
silver stipple body, amber abdomen bands, glassy wings, pink brain.
idea credited to the nerve protocol, github.com/h100envy/nerve"""
import numpy as np
import cloud as B

R = np.random.default_rng(21)


class Cloud:
    def __init__(self, parts):
        self.P = np.vstack([p[0] for p in parts])
        self.col = np.vstack([np.tile(np.array(p[1], float) / 255, (len(p[0]), 1)) for p in parts])
        self.base = np.concatenate([p[2] * (0.55 + 0.45 * R.random(len(p[0]))) for p in parts])
        self.kind = np.concatenate([np.full(len(p[0]), p[3]) for p in parts])
        n = len(self.P)
        self.act = np.zeros(n)
        self.spark = np.where(R.random(n) < 0.07, 2.4, 1.0)
        self.tint = np.zeros((n, 3)); self.tint_amt = np.zeros(n)
        self.tract_pts = np.zeros((0, 3))


def fuzz(c, r, n, length):
    p = B.ellipsoid(n, c, r, shell=0.03)
    nrm = (p - np.array(c)) / np.array(r) ** 2
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    return p + nrm * (R.random((n, 1)) ** 2) * length


def make_bee(lit_seed=3):
    rng = np.random.default_rng(lit_seed)
    br = B.Brain(head=False)
    m = br.mask("mushroom"); br.excite("mushroom", np.where(rng.random(m.sum()) < 0.06, 1.2, 0.4))
    br.excite("antennal", 0.6); br.excite("central", 0.8); br.excite("optic", 0.35)
    keep = br.L != 5                                        # drop the haze, the head is the container now
    brainP = br.P[keep] * 0.92 + np.array([0, 0.10, 0.02])
    brain_col = (br.col[keep] * 255)
    brain_base = (br.base + br.act)[keep]
    parts = []
    # brain: carry its own colours and activity
    for lobe in range(5):
        sel = br.L[keep] == lobe
        parts.append((brainP[sel], brain_col[sel][0], 0, "brain"))
    SILVER, DIM, AMBER, GLASS = (232, 230, 240), (150, 150, 165), (255, 184, 80), (200, 210, 235)
    # head capsule with fuzz
    parts.append((B.ellipsoid(9000, (0, -0.05, 0.05), (1.18, 1.02, 0.66), shell=0.05), DIM, 0.12, "shell"))
    top = fuzz((0, -0.05, 0.05), (1.18, 1.02, 0.66), 7000, 0.18); top = top[top[:, 1] > -0.1]
    parts.append((top, SILVER, 0.22, "fuzz"))
    for sx in (-1, 1):
        eye = B.ellipsoid(9000, (1.12 * sx, 0.02, 0.30), (0.30, 0.74, 0.44), shell=0.05)
        parts.append((eye, SILVER, 0.2, "eye"))
        # glossy highlight on each eye
        hl = B.ellipsoid(500, (1.16 * sx, 0.34, 0.68), (0.05, 0.09, 0.03))
        parts.append((hl, (255, 255, 255), 0.9, "hl"))
        sc = B.tube(1400, [(0.14 * sx, -0.02, 0.66), (0.20 * sx, 0.40, 0.92), (0.26 * sx, 0.72, 1.00)], 0.03)
        parts.append((sc, SILVER, 0.55, "ant"))
        fl = B.bezier(np.array((0.26 * sx, 0.72, 1.00)), np.array((0.46 * sx, 1.10, 0.96)),
                      np.array((0.70 * sx, 1.36, 0.80)), np.array((0.94 * sx, 1.46, 0.60)), 12)
        parts.append((np.vstack([c + R.normal(scale=0.034, size=(170, 3)) for c in fl]), SILVER, 0.55, "ant"))
        parts.append((B.tube(1100, [(0.30 * sx, -0.86, 0.50), (0.20 * sx, -1.06, 0.58), (0.06 * sx, -1.12, 0.60)], 0.035), SILVER, 0.35, "mand"))
    for c in ((0, 0.80, 0.40), (-0.18, 0.72, 0.44), (0.18, 0.72, 0.44)):
        parts.append((B.ellipsoid(300, c, (0.05, 0.05, 0.05)), (255, 255, 255), 0.9, "ocelli"))
    # thorax, fuzzy
    parts.append((B.ellipsoid(9000, (0, -0.15, -1.55), (1.00, 0.95, 0.95), shell=0.08), DIM, 0.16, "thorax"))
    parts.append((fuzz((0, -0.15, -1.55), (1.00, 0.95, 0.95), 16000, 0.28), SILVER, 0.2, "fuzz"))
    # abdomen with bands
    ab = B.ellipsoid(34000, (0, -0.55, -3.75), (1.05, 0.98, 1.65), shell=0.12)
    band = np.floor((ab[:, 2] + 5.4) / 0.42).astype(int) % 2
    tip = ab[:, 2] < -5.0
    parts.append((ab[(band == 0) & ~tip], AMBER, 0.5, "abd"))
    parts.append((ab[(band == 1) | tip], DIM, 0.14, "abd"))
    # wings: flat glassy ovals with brighter veins
    for sx in (-1, 1):
        for (L, Wd, ang, z0) in ((2.6, 0.95, 0.55, -1.7), (1.8, 0.62, 0.35, -2.05)):
            t = R.random(9000) * 2 * np.pi; r = np.sqrt(R.random(9000))
            u = (np.cos(t) * r + 1) / 2 * L; v = np.sin(t) * r * Wd / 2
            x = sx * (0.45 + u * np.cos(ang)); y = 0.55 + u * np.sin(ang) * 0.9 + v * 0.3
            z = z0 - u * 0.45 + v
            parts.append((np.stack([x, y, z], 1), GLASS, 0.07, "wing"))
            # outline and a few veins
            tt = np.linspace(0, 2 * np.pi, 700)
            uu = (np.cos(tt) + 1) / 2 * L; vv = np.sin(tt) * Wd / 2
            parts.append((np.stack([sx * (0.45 + uu * np.cos(ang)), 0.55 + uu * np.sin(ang) * 0.9 + vv * 0.3, z0 - uu * 0.45 + vv], 1)
                          + R.normal(scale=0.008, size=(700, 3)), GLASS, 0.45, "vein"))
    # legs, thin
    for sx in (-1, 1):
        for zz in (-1.2, -1.6, -2.0):
            parts.append((B.tube(700, [(0.8 * sx, -0.7, zz), (1.35 * sx, -1.2, zz + 0.2), (1.2 * sx, -1.9, zz + 0.4)], 0.03), DIM, 0.3, "leg"))
    cl = Cloud(parts)
    # brain activity carried over
    nb = keep.sum()
    cl.base[:nb] = np.concatenate([brain_base[br.L[keep] == lobe] for lobe in range(5)])
    return cl
