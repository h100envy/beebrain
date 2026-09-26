# security

this release holds no keys, signs nothing and places no orders.

- no wallet code, no key handling, no signing, no order routing in 0.3. `tests/test_safety.py` checks it. that test belongs to this release: the pull request that adds live execution on purpose removes it and adds its own checks.
- network: the sim makes no calls. field mode (`beebrain trade`, `beebrain scan`, the `/trade` page) only sends GET requests to the public dexscreener and geckoterminal apis. no api keys, no accounts, nothing about you is sent.
- local files: the csv you pass with `--trades`, and field sessions saved to `~/.beebrain/`. the page saves its session in your browser's localStorage and nowhere else.
- the site has no forms, no analytics and no third party scripts. fonts are self hosted. `/trade` ships a content security policy that only allows those two apis.
- token names come from public apis and anyone can set them. the page inserts them as text, never as html, and links out only to dexscreener.

live execution is on the roadmap. it will be opt in, off by default, small size, and only reachable for a bee whose paper record opened the graduation gate.

if you find a way the code could touch funds, a key or the network, or anything else that looks like a security issue, do not open a public issue. open a private report through github security advisories on this repo, or contact [@h100envy](https://github.com/h100envy). expect an answer within a few days.
