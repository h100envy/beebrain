# changelog

## 0.3.0

- the field: the same brain on live memecoin pools from solana, base, bsc and robinhood chain. read only data from dexscreener and geckoterminal.
- three paper accounts race from $500: you, the bee on autopilot, a random baseline behind the same reflexes.
- forward test: every scored pool is priced again after 15 minutes, fees in. hit rate and average net return per verdict.
- graduation gate: 300 forward tested pools, PASS beats SKIP by 5 points, bee beats random. paper only until then.
- `/trade` on the site, `beebrain trade` in the terminal, `beebrain scan --json` for your own tools. the browser and python twins are checked against each other.
- the "never any keys" rule is gone from the docs. 0.3 still places no orders; live execution is on the roadmap behind the gate.

## 0.2.0

- repo layout: the model, the market, the engine and the terminal are separate modules. `brain.py` imports no ui.
- reward signal renamed from dopamine to octopamine, the sugar channel. in insects octopamine carries appetitive reward and dopamine the aversive signal.
- separate punishment channel for losses, with its own learning rate. rug memory does not fade faster than print memory.
- `beebrain` console script with `terminal`, `sim` and `render` subcommands. every flag of the first build still works.
- `beebrain sim --seeds 0-9` reproduces the ten seed table in the article.
- `beebrain sim --vector N` prints the waggle vector of one pool as json.
- the 3d video now shows pools, verdicts and scores from an engine run instead of a scripted list.
- article figure 06 is computed by the sim at render time.
- tests, ruff, ci on python 3.9 and 3.12.
- static site in `web/`: landing page, the article, the robinhood chain page. fonts self hosted.

## 0.1.0

- first terminal build: five lobes, the waggle dance, the paper account, stage 2 (grok reader) and stage 3 (telegram).
- the reward signal was labelled dopamine. that was the mammal convention and wrong for a bee.
