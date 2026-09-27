# roadmap

the order matters. every step has to earn the next one on public numbers.

## done

- **the sim.** five lobes, sparse code, sugar and punishment channels, ten seeds pinned by tests.
- **the field.** the same brain on live pools from solana, base, bsc and robinhood chain. three paper accounts race: you, the bee, random. 15 minute forward test, fees in.
- **tools.** `beebrain scan --json`, `beebrain forage`, `beebrain report`. first field reports with raw data in `docs/field-reports`.
- **signals v0.** a PASS list on `/trade` with copy CA and browser notifications. the live ticker on the landing page.

## next: signals

- a telegram bot that posts every PASS with its waggle vector and a chart link. read only.
- `beebrain serve`: a small json api and a webhook, the same verdicts `scan` prints, for other bots.
- a trained bee for new visitors: long headless runs seed the brain, labelled with how many real pools it has seen.
- field reports on a schedule, so the forward test grows past anecdote.

## next: read only wallet scoring

- paste a public wallet address. the page pulls your past swaps from public apis and shows how the bee would have scored each one at the time.
- your own trades teach your bee. still no keys: an address is public.

## the gate

the graduation gate opens per chain when:

1. at least 300 pools are forward tested
2. PASS beats the skips the brain made by 5 points of average net return, capped
3. the bee's paper account is ahead of random

reports publish the numbers either way.

## after the gate: execution

- opt in and off by default. your own wallet signs every trade, in the browser or with a key you control in the terminal. beebrain never holds keys and never takes custody.
- hard limits you set: size per trade, trades per day, max loss per day, a kill switch.
- starts with a small size and the same exits the paper account uses, so paper and live can be compared trade by trade.

## the hive

- one bee per chain with separate antennae and a shared mushroom memory.
- the grok, jev and opus lobes from the article: the bee sends its waggle vector to the models and learns when they are right.
