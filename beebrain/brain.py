"""
beebrain.brain

the model only. no ui, no clock, no io. same rng in, same brain out.

  antennal lobes   eight glomeruli, one per pool feature. input noise is measured here
  optic lobes      the shape of the narrative: heat and acceleration
  mushroom bodies  2,000 kenyon cells, sparse code. octopamine on prints, punishment on rugs
  central complex  weighs the lobes, explore or exploit
  motor            PASS, WATCH or SKIP plus the waggle vector, one value per lobe

reward channels. in insects octopamine carries appetitive reward (vummx1, the sugar
neuron) and dopamine carries the aversive signal. so a print travels on the octopamine
channel and a rug on its own punishment channel. unlike a bee, rug memory here does not
fade faster than print memory: PUNISH_LR >= OCTOPAMINE_LR, checked at import.

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import math
from collections import deque

# ---------------------------------------------------------------- scale ---
REAL_BEE_NEURONS = 960_000
REAL_BEE_KC = 340_000         # kenyon cells, both mushroom bodies, approx

# ------------------------------------------------------ antennal lobes ---
FEATS = ["liquidity", "holders", "snipers", "bundle", "creator age", "heat", "accel", "volume"]
N_BINS = 4                    # each glomerulus reports its feature in four bins
N_INPUTS = len(FEATS) * N_BINS
ANT_NOISE_W = 0.9             # weight of measured pool noise
ANT_INCONS_W = 0.4            # weight of self contradiction between related features
ANT_JITTER = 0.03             # sd of the antennal read itself

# --------------------------------------------------------- optic lobes ---
OPTIC_HEAT_W = 0.55
OPTIC_ACCEL_W = 0.45

# ----------------------------------------------------- mushroom bodies ---
N_KC = 2000
KC_FANIN = 6                  # inputs sampled by each kenyon cell
KC_ACTIVE = 100               # 5% sparse code, exactly this many fire per pool
KC_TIE = 0.01                 # tiny fixed per cell bias that breaks ties in the top k
W_INIT = 0.5                  # kenyon cell to output synapse, start neutral
MB_GAIN = 2.2                 # spreads the mean synapse weight around 0.5
MEMORY_LEN = 800              # recent (sparse code, outcome) pairs kept for the seen tally
SEEN_OVERLAP = 0.4            # share of cells two codes must share to count as the same shape

# reward and punishment channels
OCTOPAMINE_LR = 0.25          # sugar: a closed trade in profit
PUNISH_LR = 0.25              # punishment: a closed trade at a loss
GHOST_LR = 0.06               # a skipped pool still teaches a little, on the same two channels

# ---------------------------------------------------- central complex ---
W_MUSHROOM = 0.5
W_OPTIC = 0.2
W_ANTENNAL = 0.2
W_SNIPERS = 0.1               # applied to 1 - sniper share
EPS_START = 0.5               # explore rate with an empty memory
EPS_FLOOR = 0.05
EPS_TAU = 15                  # resolved trades per e-fold of the explore rate

# --------------------------------------------------------------- motor ---
PASS_AT = 0.58
PASS_MIN_ANTENNAL = 0.35      # a pass needs at least this clean an input
WATCH_AT = 0.47
FLAG_BELOW = 0.50             # a pass with antennal below this carries a flag
CONSENSUS_GAIN = 2.5

# ------------------------------------------------- ninth glomerulus ---
FEATS9 = FEATS + ["tg velocity"]
TG_LOUD = 0.70                # telegram velocity above this is a loud room
CROSS = 32                    # cross modal cells: loud or quiet x 8 features x high or low
CROSS_MIN_N = 10              # a pairing says nothing before this many outcomes
CROSS_Z = 2.2                 # and nothing until it is this many standard errors off base
CROSS_GAIN = 0.9
BASE_START = 0.35
BASE_LR = 0.01

if PUNISH_LR < OCTOPAMINE_LR:
    raise ValueError("rug memory must not fade faster than print memory: PUNISH_LR >= OCTOPAMINE_LR")


def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


class BeeBrain:
    def __init__(self, rng):
        self.rng = rng
        # kenyon cells: each samples KC_FANIN of the binned glomerulus outputs
        self.kc_in = [rng.sample(range(N_INPUTS), KC_FANIN) for _ in range(N_KC)]
        self.tie = [rng.random() * KC_TIE for _ in range(N_KC)]
        self.w = [W_INIT] * N_KC               # kc -> output neuron weights
        self.memory = deque(maxlen=MEMORY_LEN)  # (active set, won)
        self.eps = EPS_START
        self.resolved = 0
        self.sugar = 0                         # octopamine broadcasts
        self.pain = 0                          # punishment broadcasts

    # ------------------------------------------------ mushroom bodies ---
    def code(self, obs):
        """sparse code: the KC_ACTIVE cells with the most matching inputs fire"""
        on = set()
        for i, f in enumerate(FEATS):
            on.add(i * N_BINS + min(N_BINS - 1, int(obs[f] * N_BINS)))
        score = [(sum(1 for j in ins if j in on) + self.tie[k], k)
                 for k, ins in enumerate(self.kc_in)]
        score.sort(reverse=True)
        return frozenset(k for _, k in score[:KC_ACTIVE])

    def value(self, act):
        return sum(self.w[k] for k in act) / KC_ACTIVE

    # ------------------------------------------------------ one pool ---
    def think(self, pool, heat_hist):
        o = pool.obs
        # antennal lobes: noise estimate from disagreement between related signals
        incons = abs(o["volume"] - o["liquidity"]) * 0.5 + abs(o["holders"] - (1 - o["snipers"])) * 0.5
        antennal = clamp(1.0 - ANT_NOISE_W * pool.noise - ANT_INCONS_W * incons + self.rng.gauss(0, ANT_JITTER))
        # optic lobes: the shape of the narrative
        optic = clamp(OPTIC_HEAT_W * o["heat"] + OPTIC_ACCEL_W * o["accel"])
        # mushroom bodies: sparse code, learned value, how often this shape was seen
        act = self.code(o)
        mb_val = self.value(act)
        seen = won = 0
        for s, w_ in self.memory:
            if len(act & s) >= KC_ACTIVE * SEEN_OVERLAP:
                seen += 1
                won += w_
        mushroom = clamp(0.5 + (mb_val - 0.5) * MB_GAIN)
        # central complex: weighs lobes, explore vs exploit
        comb = (W_MUSHROOM * mushroom + W_OPTIC * optic + W_ANTENNAL * antennal
                + W_SNIPERS * (1 - o["snipers"]))
        explore = self.rng.random() < self.eps
        central = comb
        # motor
        if o["bundle"] > 0.5:
            verdict = "SKIP"
        elif comb >= PASS_AT and antennal >= PASS_MIN_ANTENNAL:
            verdict = "PASS"
        elif comb >= WATCH_AT:
            verdict = "WATCH"
        else:
            verdict = "SKIP"
        flag = verdict == "PASS" and antennal < FLAG_BELOW
        take = verdict == "PASS" or (verdict == "WATCH" and explore)
        lobes = {"mushroom": mushroom, "antennal": antennal, "optic": optic, "central": central}
        vals = list(lobes.values())
        m = sum(vals) / 4
        consensus = 1 - math.sqrt(sum((v - m) ** 2 for v in vals) / 4) * CONSENSUS_GAIN
        return dict(act=act, lobes=lobes, seen=seen, won=won, verdict=verdict, flag=flag,
                    explore=explore and verdict == "WATCH", take=take,
                    consensus=clamp(consensus), comb=comb)

    # ------------------------------------------------------ learning ---
    def octopamine(self, act, lr=OCTOPAMINE_LR):
        """sugar channel. only the kenyon cells that fired for this pool move toward print."""
        self.sugar += 1
        for k in act:
            self.w[k] += lr * (1.0 - self.w[k])

    def punish(self, act, lr=PUNISH_LR):
        """punishment channel. only the kenyon cells that fired for this pool move toward rug."""
        self.pain += 1
        for k in act:
            self.w[k] += lr * (0.0 - self.w[k])

    def learn(self, act, won, lr):
        if won:
            self.octopamine(act, lr)
        else:
            self.punish(act, lr)

    def after_trade(self, act, won):
        self.learn(act, won, OCTOPAMINE_LR if won else PUNISH_LR)
        self.memory.append((act, 1 if won else 0))
        self.resolved += 1
        self.eps = max(EPS_FLOOR, EPS_START * math.exp(-self.resolved / EPS_TAU))


class BeeBrain9(BeeBrain):
    """same brain, nine glomeruli.
    the 2,000 on-chain kenyon cells work exactly as before. on top, a small set of cross modal
    cells, one for every pairing of a telegram level with an on-chain feature level
    (loud or quiet x 8 features x high or low = 32 cells). each keeps its own tally of what
    followed. its output is trusted in proportion to how often it has fired, so an unproven
    pairing says nothing and a proven one speaks loudly. nothing tells it which pairing matters."""

    def __init__(self, rng):
        super().__init__(rng)
        self.cross_n = [0] * CROSS
        self.cross_w = [0] * CROSS
        self.base = BASE_START

    def code(self, obs):
        act = set(super().code(obs))
        tb = 1 if obs["tg velocity"] > TG_LOUD else 0
        for fi, f in enumerate(FEATS):
            act.add(N_KC + (tb * 8 + fi) * 2 + (1 if obs[f] > 0.5 else 0))
        return frozenset(act)

    def value(self, act):
        base_cells = [self.w[k] for k in act if k < N_KC]
        v1 = sum(base_cells) / max(1, len(base_cells))
        d = 0.0
        for k in act:
            if k >= N_KC:
                i = k - N_KC
                n = self.cross_n[i]
                if n >= CROSS_MIN_N:
                    rate = (self.cross_w[i] + 1) / (n + 2)
                    se = math.sqrt(self.base * (1 - self.base) / n)
                    if abs(rate - self.base) > CROSS_Z * se:     # a pairing speaks only once it is proven
                        d += (rate - self.base) * n / (n + 8)
        return clamp(v1 + CROSS_GAIN * d)

    def _tally(self, act, won):
        for k in act:
            if k >= N_KC:
                self.cross_n[k - N_KC] += 1
                self.cross_w[k - N_KC] += 1 if won else 0

    def octopamine(self, act, lr=OCTOPAMINE_LR):
        self.sugar += 1
        for k in act:
            if k < N_KC:
                self.w[k] += lr * (1.0 - self.w[k])
        self._tally(act, True)

    def punish(self, act, lr=PUNISH_LR):
        self.pain += 1
        for k in act:
            if k < N_KC:
                self.w[k] += lr * (0.0 - self.w[k])
        self._tally(act, False)

    def learn(self, act, won, lr):
        self.base += BASE_LR * ((1.0 if won else 0.0) - self.base)
        super().learn(act, won, lr)

    def probe(self, vel, age):
        o = {"liquidity": 0.5, "holders": 0.5, "snipers": 0.2, "bundle": 0.0, "creator age": age,
             "heat": 0.5, "accel": 0.5, "volume": 0.5, "tg velocity": vel}
        return clamp(0.5 + (self.value(self.code(o)) - 0.5) * MB_GAIN)


def waggle_vector(pool, thought):
    """the output of one pool as plain data. one value per lobe, not one number."""
    L = thought["lobes"]
    return {
        "pool": pool.name,
        "mushroom": {"value": round(L["mushroom"], 2), "seen": thought["seen"], "printed": thought["won"]},
        "antennal": {"value": round(L["antennal"], 2), "noise": round(pool.noise, 2)},
        "optic": {"value": round(L["optic"], 2), "heat": round(pool.obs["heat"], 2),
                  "accel": round(pool.obs["accel"], 2)},
        "central": {"value": round(L["central"], 2), "mode": "explore" if thought["explore"] else "exploit"},
        "motor": {"verdict": thought["verdict"], "flag": thought["flag"]},
        "consensus": round(thought["consensus"], 2),
        "kenyon_active": len([k for k in thought["act"] if k < N_KC]),
    }
