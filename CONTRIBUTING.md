# contributing

small pull requests, one idea each.

## setup

```
pip install -e '.[dev]'
pytest -q
ruff check .
```

the render and figure scripts need the extras:

```
pip install -e '.[render,figures]'
python -m playwright install chromium
```

## rules

- the package and the terminal stay stdlib only. numpy, scipy, pillow and playwright are for `render/` and `brand/`.
- `brain.py` imports nothing from the ui and stays deterministic for a given seed.
- every number on screen comes from the running simulation. no hardcoded results in the ui, the figures or the site.
- keep the labels that say sim, synthetic pools and paper account. do not remove or soften them.
- no wallet, key, signing, rpc write or order code. a test fails if it shows up.
- if a change moves the ten seed table, say so in the pull request and update `tests/test_engine.py` and the article together.
- prose and comments: lowercase, short sentences, no hype, no emoji, no em dashes.
