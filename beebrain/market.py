"""
beebrain.market

synthetic memecoin pools. nothing here touches a chain.

every pool carries a hidden win probability. the brain never sees it. it only sees
noisy observations of eight features and, later, whether the trade printed or rugged.

the planted edge (stage 1)

  good = 1.7 * creator age
       + 1.0 * [heat > 0.5 and accel > 0.5]
       - 1.6 * snipers
       - 1.3 * bundle
       + 0.6 * liquidity
       + 0.3 * holders
       - 0.95
       + gauss(0, 0.35)
  p_win = sigmoid(3.0 * good)

creator age carries most of it. this edge was put here on purpose so the mechanism has
something to find. a run that finds it proves the mechanism, not the market.

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
from .brain import clamp, sigmoid

SYL = ["zor", "ka", "neo", "pip", "mo", "rex", "lu", "ba", "tron", "fi", "gor",
       "wen", "kit", "sol", "ra", "vex", "nu", "chi", "bon", "hive", "buzz"]
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

# ------------------------------------------------------ narrative heat ---
HEAT_START = 0.35
HEAT_MEAN = 0.4
HEAT_REVERT = 0.05            # pull toward the mean per pool
HEAT_VOL = 0.03
META_P = 0.02                 # chance a new meta catches on this pool
META_JUMP = (0.2, 0.35)
HEAT_MIN, HEAT_MAX = 0.05, 0.97
HEAT_HIST = 60                # ticks the optic lobes can see
ACCEL_LAG = 10

# ---------------------------------------------------------------- pool ---
BUNDLE_P = 0.22               # share of launches that are bundled
OBS_NOISE = 0.28              # observation sd per unit of pool noise

# the planted edge, see the module docstring
EDGE_CREATOR = 1.7
EDGE_META = 1.0
EDGE_SNIPERS = 1.6
EDGE_BUNDLE = 1.3
EDGE_LIQUIDITY = 0.6
EDGE_HOLDERS = 0.3
EDGE_BIAS = 0.95
EDGE_SD = 0.35
EDGE_SHARP = 3.0

# ------------------------------------------------ stage 2: dirty pools ---
DIRTY_EXTRA = 0.25            # extra noise on stage 2 pools
RUG_BASE = 0.02
RUG_SLOPE = 1.1               # model assumption: rug odds rise with noise above RUG_KNEE
RUG_KNEE = 0.35
RUG_LOSS = (0.80, 0.95)

# ---------------------------------------------- stage 3: telegram edge ---
VEL_HI = 0.70                 # a loud room
AGE_OLD = 0.50                # a creator with a history
TG_EDGE_BONUS = 0.8           # loud room and old creator
TG_EDGE_TRAP = 0.25           # loud room and new creator
TG_EDGE_SHARP = 2.6

WIN_RANGE = (0.3, 1.6)
LOSS_RANGE = (0.25, 0.7)


def step_heat(rng, heat):
    """one tick of narrative heat: mean reverting with occasional metas catching"""
    heat += HEAT_REVERT * (HEAT_MEAN - heat) + rng.gauss(0, HEAT_VOL)
    if rng.random() < META_P:
        heat += rng.uniform(*META_JUMP)
    return clamp(heat, HEAT_MIN, HEAT_MAX)


def observe(rng, true, noise):
    return {k: (v if k == "bundle" else clamp(v + rng.gauss(0, OBS_NOISE * noise)))
            for k, v in true.items()}


class Pool:
    def __init__(self, rng, i, heat, accel):
        self.id = i
        self.name = ("$" + "".join(rng.choice(SYL) for _ in range(rng.choice((1, 2, 2)))).upper())[:10]
        a = "".join(rng.choice(B58) for _ in range(44))
        self.addr = a[:4] + "…" + a[-4:]
        self.noise = rng.betavariate(2, 5)
        t = {
            "liquidity": rng.betavariate(2, 3),
            "holders": rng.betavariate(2, 2.5),
            "snipers": rng.betavariate(2, 5),
            "bundle": 1.0 if rng.random() < BUNDLE_P else 0.0,
            "creator age": rng.betavariate(1.5, 3),
            "heat": clamp(heat + rng.gauss(0, 0.06)),
            "accel": clamp(0.5 + accel * 3 + rng.gauss(0, 0.05)),
            "volume": rng.betavariate(2, 3),
        }
        self.true = t
        # the hidden edge the brain has to discover. creator age carries most of it.
        good = (EDGE_CREATOR * t["creator age"] + EDGE_META * (t["heat"] > 0.5) * (t["accel"] > 0.5)
                - EDGE_SNIPERS * t["snipers"] - EDGE_BUNDLE * t["bundle"] + EDGE_LIQUIDITY * t["liquidity"]
                + EDGE_HOLDERS * t["holders"] - EDGE_BIAS + rng.gauss(0, EDGE_SD))
        self.p_win = sigmoid(EDGE_SHARP * good)
        self.obs = observe(rng, t, self.noise)


def dirty(pool, rr):
    """stage 2: dirtier data, the kind that makes lobes disagree"""
    pool.noise = clamp(pool.noise + rr.uniform(0.0, DIRTY_EXTRA))
    pool.obs = observe(rr, pool.true, pool.noise)


def settle_rug(pool, rr):
    """stage 2: fix the outcome at birth. contradicting, noisy data is where rugs hide."""
    pool.rug = rr.random() < clamp(RUG_BASE + RUG_SLOPE * max(0.0, pool.noise - RUG_KNEE))
    if pool.rug:
        pool.final = -rr.uniform(*RUG_LOSS)
    else:
        pool.final = rr.uniform(*WIN_RANGE) if rr.random() < pool.p_win else -rr.uniform(*LOSS_RANGE)


def telegram(pool, rr, heat):
    """stage 3: a ninth feature and a new planted edge. a loud room pays only when the creator has a history."""
    v = clamp(rr.betavariate(2.0, 2.6) + 0.25 * max(0.0, heat - 0.5))
    pool.true["tg velocity"] = v
    pool.obs["tg velocity"] = clamp(v + rr.gauss(0, 0.05))
    t = pool.true
    ca = t["creator age"]
    good = (0.6 * t["liquidity"] - 1.2 * t["snipers"] - 1.3 * t["bundle"] + 0.4 * ca
            + TG_EDGE_BONUS * (v > VEL_HI) * (ca > AGE_OLD) - TG_EDGE_TRAP * (v > VEL_HI) * (ca <= AGE_OLD)
            - 0.30 + rr.gauss(0, 0.35))
    pool.p_win = sigmoid(TG_EDGE_SHARP * good)
    pool.rug = False
    pool.final = rr.uniform(*WIN_RANGE) if rr.random() < pool.p_win else -rr.uniform(*LOSS_RANGE)
    pool.ct_lag = rr.uniform(12, 95) if v > VEL_HI else None
    return v
