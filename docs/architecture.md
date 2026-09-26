# architecture

```
beebrain/
  brain.py      the model. no ui, no io. glomeruli, kenyon cells, sparse code, learning,
                central complex, motor, waggle vector
  market.py     synthetic pools and the planted edge
  engine.py     paper account, positions, fees, the sugar and punishment broadcast.
                stage 2 (grok reader) and stage 3 (telegram) engines
  live.py       reads your own closed trades from a csv, read only
  cli.py        beebrain terminal | sim | render
  terminal/     the ansi ui, stdlib only
    canvas.py   canvas, palette, tones, glyphs
    art.py      the drawn brain, the 3d brain, the lab spike sims. display only
    shows.py    drives one pool through the brain over a few frames
    panels.py   stage 1 panels, header, account, log
    grok.py     stage 2 panels
    telegram.py stage 3 panels and the lab look
    app.py      the loop, layout and window size
render/         numpy point cloud brain, bee head, the 3d video and stills
brand/          article figures, cover, avatar, banner, favicons, the readme gif
web/            the static site
docs/           article, model, limitations, this file
tests/          pytest, no network
```

## one pool

```
market.Pool  ──▶  brain.think  ──▶  engine.act  ──▶  position opens
                     │                                  │
                     └── waggle vector                  ▼
                                               engine.tick_positions
                                                        │  closes after 8 to 26 pools
                                                        ▼
                                  brain.octopamine (print) or brain.punish (rug)
                                  only on the kenyon cells that fired for that pool
```

`Engine.step()` is `next_pool`, `tick_positions`, `act`. a headless run calls it in a loop. the terminal calls
the same three methods, spread over a few frames so you can watch each lobe light up. the drawing code has its
own random generator, so watching never changes the run.

## determinism

one `random.Random(seed)` feeds the market, the brain and the account, in a fixed order. `Engine(seed, record=True)`
keeps every log line, and `event_hash()` hashes them. the tests check that the same seed gives the same hash.

## boundaries

- no network, no chain, no wallet. the only file the package reads is the csv you pass with `--trades`.
- the terminal and the package are stdlib only. numpy, scipy and pillow are for `render/`,
  playwright for `brand/`. both are optional extras.
- the engine logs tones (`good`, `bad`, `wait`), not colours. the terminal maps tones to colours.

## where it sits in nerve

after the reflexes, before the models. the reflex layer kills the obvious rugs without a model call. the bee only
sees pools that survived, and sends the waggle vector on. this repo is the bee on its own, on synthetic pools.
the wiring into nerve lives at [github.com/h100envy/nerve](https://github.com/h100envy/nerve).
