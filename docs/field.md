# the field

the sim proves the mechanism on pools where the edge was planted. the field asks the real question: does the
bee find anything on real pools?

field mode drops the same brain on live memecoin pools and trades paper money next to you. it runs in three places:

| where | how |
| --- | --- |
| the site | `/trade`, nothing to install. the bee lives in your browser's storage and keeps learning between visits |
| the terminal | `beebrain trade --chain solana`. keys: `b` buy the last pass with $50, `s` sell your oldest, `q` quit. saved to `~/.beebrain/` |
| your own tools | `beebrain scan --chain solana --json`: one pass over the live field, every pool with its verdict, reflexes and waggle vector |
| a study | `beebrain forage --chain solana --minutes 60 --out f.json`, then `beebrain report f.json`: forward test per verdict, what the reflexes caught, the race, and the rank correlation of each sense with the 15 minute outcome |

the browser and the terminal run the same code twice: `web/trade/bee.js` and `beebrain/field/`. the same wiring
(mulberry32, seed 5), the same constants, the same senses. `tests/test_field.py` feeds both the same real pools
under node and python and checks they agree to the last bit.

## data

read only, public, no keys.

| source | what | how often |
| --- | --- | --- |
| dexscreener `token-profiles/latest`, `token-boosts/latest`, `token-boosts/top` | discovery | every 30 s |
| dexscreener `tokens/v1/{chain}` | the best pool for each discovered token | with discovery |
| geckoterminal `networks/{net}/new_pools` and `trending_pools?duration=5m`, in turn | the newest and the hottest pools | every 90 s, doubles on 429, up to 10 min |
| dexscreener `latest/dex/pairs/{chain}` | prices for open positions and forward tests, 30 pairs a call | every 15 s |

chains: solana, base, bsc, robinhood chain (dexscreener only). pools older than 30 days or above $200m fdv are left out,
they are not launches.

## senses

the eight glomeruli keep their slots. only what they smell changes. see `beebrain/field/features.py`.

| slot | live sense | formula |
| --- | --- | --- |
| liquidity | liquidity | `(log10(liq) - 3) / 3`, $1k = 0, $1m = 1 |
| holders | buys 1h | `log10(1 + buys_h1) / 3.3` |
| snipers | sell pressure | `sells_m5 / (buys_m5 + sells_m5)`, 0.5 under 4 trades |
| bundle | reflex | 1 when any reflex trips. the motor always skips it |
| creator age | pool age | `log10(1 + minutes) / log10(1 + 4320)`, 3 days = 1 |
| heat | heat | rank of this pool's hourly volume among the pools in view |
| accel | acceleration | half 5 minute volume pace against the hour, half 5 minute price move |
| volume | turnover | `log10(1 + 10 * vol_h1 / liq) / 2` |

noise, the thing the antennal lobes measure, is thin data: `1 - log10(1 + trades_h1) / 3`.

## reflexes

deterministic kills before the brain, like nerve's reflex layer.

| reflex | trips when |
| --- | --- |
| no pool liquidity yet, bonding curve | liquidity is zero |
| thin liquidity | under `REFLEX_MIN_LIQ` = $2,000 |
| fdv far above liquidity | fdv over `REFLEX_FDV_LIQ` = 250 x liquidity |
| no sells, possible honeypot | `REFLEX_HONEYPOT_BUYS` = 25 buys in an hour and no sell |
| dumping now | 5 minute change at or below -50% |
| rugged in the last hour | 1 hour change at or below -80% |

## three accounts

all start at $500 of paper.

- **you.** buy the pool in focus for $25, $50 or $100. sell whenever.
- **the bee.** enters every PASS, and a WATCH when it explores, sized like the sim: 13% of equity, 4% on explore, at most 4 open.
- **random.** enters pools that passed the reflexes at random, at the bee's own entry rate, same size, same exits. the reflexes are nerve's, not the bee's, so this baseline isolates what the bee learned.

fills: the quoted price, plus impact `2 * size / liquidity`, plus a 1% fee each way. open positions are marked at what they
would fetch if sold now. exits for the bee and random: take profit at +100%, stop at -35%, 30 minute max hold, or a rug
(liquidity under 30% of entry, or price down 90%). your positions follow the same exits.

a closed bee trade is broadcast into memory: sugar for a profit, punishment for a loss, only on the kenyon cells that
fired for that pool.

## forward test

every scored pool is written down with its price. 15 minutes later its price is read again. net return, fees in:
`(p15 / p0) * 0.98 - 1`. that gives each verdict a hit rate and an average net return on the real market, whether or
not anybody traded. pools the bee did not take teach it through the ghost channel, like skipped pools in the sim.

## graduation gate

the gate opens when all three hold:

1. at least `GRADUATE_POOLS` = 300 forward tested pools
2. PASS beats SKIP by at least `GRADUATE_EDGE` = 5 points of average net return
3. the bee's paper account is ahead of the random baseline

an open gate means the bee has earned a look at real money. it does not wire anything. live execution is on the roadmap,
opt in, small size, and only for a bee that opened the gate.
