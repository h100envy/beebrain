# model

every formula and threshold in the brain and the market, with the constant name used in code.
the model lives in `beebrain/brain.py`, the pools in `beebrain/market.py`, the account in `beebrain/engine.py`.

everything is driven by one `random.Random(seed)`. same seed, same run, byte for byte.

## scale

| constant | value | meaning |
| --- | --- | --- |
| `REAL_BEE_NEURONS` | 960,000 | neurons in a real honeybee brain, shown for scale |
| `REAL_BEE_KC` | 340,000 | kenyon cells, both mushroom bodies, approx |
| `N_KC` | 2,000 | kenyon cells simulated |

## antennal lobes

eight glomeruli, one per feature in `FEATS`: liquidity, holders, snipers, bundle, creator age, heat, accel, volume.
each reports its feature in `N_BINS` = 4 bins, so the mushroom bodies see `N_INPUTS` = 32 binary inputs.

input quality:

```
incons   = 0.5 * |volume - liquidity| + 0.5 * |holders - (1 - snipers)|
antennal = clamp(1 - ANT_NOISE_W * noise - ANT_INCONS_W * incons + gauss(0, ANT_JITTER))
```

| constant | value |
| --- | --- |
| `ANT_NOISE_W` | 0.9 |
| `ANT_INCONS_W` | 0.4 |
| `ANT_JITTER` | 0.03 |

## optic lobes

```
optic = clamp(OPTIC_HEAT_W * heat + OPTIC_ACCEL_W * accel)
```

`OPTIC_HEAT_W` = 0.55, `OPTIC_ACCEL_W` = 0.45. heat history is `HEAT_HIST` = 60 ticks.

## mushroom bodies

each kenyon cell samples `KC_FANIN` = 6 of the 32 inputs, fixed at birth. for a pool, a cell's drive is the
number of its inputs that are on, plus a fixed tie breaker below `KC_TIE` = 0.01. the top `KC_ACTIVE` = 100
cells fire. that is the sparse code: exactly 5% of cells, every pool.

```
value    = mean(w[k] for k in active)
mushroom = clamp(0.5 + (value - 0.5) * MB_GAIN)          MB_GAIN = 2.2
```

every synapse starts at `W_INIT` = 0.5.

seen tally: the last `MEMORY_LEN` = 800 (code, outcome) pairs are kept. a past code counts as the same shape
when it shares at least `SEEN_OVERLAP` * `KC_ACTIVE` = 40 cells.

## reward and punishment

two channels, like the bee. only the cells that fired for that pool are touched.

```
octopamine (print):  w[k] += OCTOPAMINE_LR * (1 - w[k])
punishment (rug):    w[k] += PUNISH_LR     * (0 - w[k])
```

| constant | value | when |
| --- | --- | --- |
| `OCTOPAMINE_LR` | 0.25 | a closed trade in profit after fees |
| `PUNISH_LR` | 0.25 | a closed trade at a loss after fees |
| `GHOST_LR` | 0.06 | a pool the bee did not take, scored on what it would have done, same two channels |

there is no passive forgetting. a print memory only fades when punishment lands on the same cells, and a rug
memory only fades when sugar does. so rug memory fades at `OCTOPAMINE_LR` and print memory at `PUNISH_LR`.
the module refuses to import if `PUNISH_LR < OCTOPAMINE_LR`, so rug memory can never fade faster than
print memory. this goes against the bee on purpose. a creator who rugged once is not forgiven because time passed.

in insects octopamine carries appetitive reward (vummx1) and dopamine the aversive signal. the first terminal
build called the reward signal dopamine. that was the mammal convention and it is fixed.

## central complex

```
comb = W_MUSHROOM * mushroom + W_OPTIC * optic + W_ANTENNAL * antennal + W_SNIPERS * (1 - snipers)
```

`W_MUSHROOM` = 0.5, `W_OPTIC` = 0.2, `W_ANTENNAL` = 0.2, `W_SNIPERS` = 0.1.

explore rate:

```
eps = max(EPS_FLOOR, EPS_START * exp(-resolved / EPS_TAU))
```

`EPS_START` = 0.5, `EPS_FLOOR` = 0.05, `EPS_TAU` = 15 resolved trades.

## motor

| rule | verdict |
| --- | --- |
| bundle is set | SKIP, always |
| comb >= `PASS_AT` (0.58) and antennal >= `PASS_MIN_ANTENNAL` (0.35) | PASS |
| comb >= `WATCH_AT` (0.47) | WATCH |
| otherwise | SKIP |

a PASS with antennal below `FLAG_BELOW` = 0.50 carries a flag. a WATCH is taken only when the explore draw hits.

consensus between the four lobe values:

```
consensus = clamp(1 - CONSENSUS_GAIN * stdev(mushroom, antennal, optic, central))      CONSENSUS_GAIN = 2.5
```

## waggle vector

`brain.waggle_vector(pool, thought)` returns one value per lobe, not one number. print one with
`beebrain sim --seeds 5 --vector 120`.

## account

| constant | value | meaning |
| --- | --- | --- |
| `START_CASH` | 500 | paper account, usd |
| `POOLS_PER_DAY` | 40 | pools per simulated day |
| `FEE` | 0.02 | round trip, charged once when a position closes |
| `MAX_OPEN` | 4 | open positions at most |
| `SIZE_PASS` | 0.13 | share of equity on a pass |
| `SIZE_EXPLORE` | 0.04 | share of equity on an explore entry |
| `MIN_SIZE` | 5 | usd, smaller entries are dropped |
| `LIFE` | 8 to 26 | pools a position stays open |
| `HOLD_WARN` | -0.30 | logged once when an open position is this far under |

equity is cash plus every open position marked at its current return. a close pays
`size * (1 + final) * (1 - FEE)`.

## market

narrative heat, one tick per pool:

```
heat += HEAT_REVERT * (HEAT_MEAN - heat) + gauss(0, HEAT_VOL)
if random() < META_P: heat += uniform(META_JUMP)
heat  = clamp(heat, HEAT_MIN, HEAT_MAX)
accel = heat - heat 10 ticks ago                                   ACCEL_LAG = 10
```

`HEAT_REVERT` = 0.05, `HEAT_MEAN` = 0.4, `HEAT_VOL` = 0.03, `META_P` = 0.02, `META_JUMP` = 0.2 to 0.35.

the planted edge, stage 1:

```
good  = EDGE_CREATOR * creator_age + EDGE_META * [heat > 0.5 and accel > 0.5]
      - EDGE_SNIPERS * snipers - EDGE_BUNDLE * bundle + EDGE_LIQUIDITY * liquidity
      + EDGE_HOLDERS * holders - EDGE_BIAS + gauss(0, EDGE_SD)
p_win = sigmoid(EDGE_SHARP * good)
```

| constant | value |
| --- | --- |
| `EDGE_CREATOR` | 1.7 |
| `EDGE_META` | 1.0 |
| `EDGE_SNIPERS` | 1.6 |
| `EDGE_BUNDLE` | 1.3 |
| `EDGE_LIQUIDITY` | 0.6 |
| `EDGE_HOLDERS` | 0.3 |
| `EDGE_BIAS` | 0.95 |
| `EDGE_SD` | 0.35 |
| `EDGE_SHARP` | 3.0 |

`BUNDLE_P` = 0.22 of launches are bundled. observations add `gauss(0, OBS_NOISE * noise)` to each feature,
`OBS_NOISE` = 0.28, pool noise drawn from beta(2, 5).

a win closes at +30% to +160%, a loss at -25% to -70%.

## stage 2 and stage 3

stage 2 (`--post 2`) adds `DIRTY_EXTRA` = 0.25 noise and rugs whose odds rise with noise above
`RUG_KNEE` = 0.35. a rule based reader waits one cycle when antennal is below `DIRTY` = 0.50 but memory
(`STRONG_MB` = 0.52) or shape (`STRONG_OL` = 0.56) says yes. it is not the grok api.

stage 3 (`--post 3`) adds a ninth glomerulus for telegram velocity and 32 cross modal cells. a pairing speaks
only after `CROSS_MIN_N` = 10 outcomes and `CROSS_Z` = 2.2 standard errors off base. the planted edge:
a loud room (`VEL_HI` = 0.70) pays only when the creator is old (`AGE_OLD` = 0.50).
