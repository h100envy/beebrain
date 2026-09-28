# BeeBrain roadmap

**Current stage: launching $BEEBRAIN on Solana.** The foundation is built. The official Solana contract address is listed below.

![BeeBrain roadmap: token launch on Solana is the current milestone](media/roadmap.svg)

[Download the PNG](media/roadmap.png) · [Project README](../README.md) · [Token details](../README.md#token)

Milestones describe the development order, not fixed release dates. Status reviewed on 28 September 2026. “Built” means implemented in the repository; hosted uptime is a separate operational check.

## 01 · The foundation

**Status: built.**

- Five brain lobes, 2,000 Kenyon cells, 5% sparse activation, separate reward and punishment channels.
- Pool scanning and adapters for Solana, Base, BSC and Robinhood chain. These are supported data sources; the BeeBrain token launches on **Solana**.
- PASS / WATCH / SKIP verdicts, browser notifications and paper accounts for the user, bee and random baseline.
- Telegram CA scoring, scans, PASS alerts and individual paper accounts.
- Fifteen-minute forward testing, headless field reports, JSON scans and seeded memory. The Solana training seed comes from an 844-pool run.
- Live terminal, 3D brain visuals and project website.

Evidence: [model](model.md), [field](field.md), [Telegram bot](bot.md), [published reports and raw data](field-reports/).

## 02 · Token launch

**Status: current milestone. We are here.**

| Item | Status |
| --- | --- |
| Ticker | **$BEEBRAIN** |
| Network | **Solana** |
| Contract address | `FW1FhMWeGwyLQLt8HaZ7Zjkoecf7FZNSw8ZC3fMApump` |
| Product foundation | Built |
| Launch visuals and CA templates | Prepared locally |
| Official address publication | CA supplied; launch materials and official pages are being updated |

Launch sequence:

1. Receive and confirm the full Solana contract address.
2. Export the post visuals and videos with that exact CA first.
3. Add the same address to the README and homepage, including the copy button; verify the full address matches everywhere.
4. Publish the repository and site updates, then check the public copies.

Completion means the launch has occurred and the confirmed address is visible consistently across the official materials. This phase does not imply that the current paper-trading engine places real orders. Staking, revenue sharing and token-gated access are not defined in this roadmap.

## 03 · Team + reliability

**Status: next. Hiring is planned; reliability and history changes are prepared locally, and the hosted rollout is not yet verified.**

Project proceeds will be directed to development and hiring senior developers. Their mandate is to bring BeeBrain to live trading: strengthen the data and execution infrastructure, implement risk controls, and test and validate real-order execution before release.

Senior engineering hires and a funded development effort are the next team milestone. Live trading remains conditional on the evaluation gate and execution checks in phase 06.

- Retry transient Telegram startup and polling errors; recover the command menu without stopping message handling.
- Release `/history` with verdict filters, prices, observation times and fee-adjusted outcomes; persist history across restarts.
- Release `/status` and a read-only configuration check, with a supervised deployment and persistent state directory.
- Verify commands, alerts, restart recovery and saved history on the actual hosted instance before calling the update shipped.

**Completion check:** a deployed instance passes these operational checks and retains its state across restarts.

## 04 · Evidence + API

**Status: next.**

- Publish field reports regularly, including sample sizes, losses, missing observations and the random baseline.
- Refresh trained seeds from documented runs. Keep training data separate from evaluation data.
- Add a JSON service and optional webhooks for the same scores produced by the CLI.
- Include chain, pool address, scoring timestamp, lobe vector and observation status in each event.

**Completion check:** reports can be reproduced from stored run data, seeds identify their source runs, API scores match the CLI and webhook retries do not duplicate events.

## 05 · The Hive

**Status: planned.**

- Read-only public wallet scoring, with supported chains and historical data coverage stated explicitly.
- Historical scores must use features available at the time of the trade; missing data stays visible.
- A learning bee for each chain, comparing separate memory with shared-memory experiments.
- Explore optional external model readers of the waggle vector; they are not part of the current five-lobe core.

**Completion check:** results identify data timestamps, and shared-memory changes demonstrate value on held-out outcomes before becoming defaults.

## 06 · Opt-in execution

**Status: conditional on the evaluation gate.**

The gate is evaluated per chain:

1. At least **300 pools** have forward-tested outcomes.
2. PASS average capped net return exceeds the brain's own SKIP by **at least 5 percentage points**.
3. The bee's paper account is ahead of the random baseline.

The published initial reports have not earned graduation. Token launch does not bypass this gate.

After meeting the criteria, the plan is user-controlled wallet signing, no custody, position-size limits, daily trade and loss limits, and a kill switch. Execution is off by default. Small live positions must be compared with the paper strategy, including fees and slippage.

**Completion check:** published evaluation criteria are met, execution controls are tested, and the user explicitly enables signing.
