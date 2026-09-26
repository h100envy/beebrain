# security

beebrain holds no keys, signs nothing and places no orders.

- no wallet code, no private key handling, no signing, no rpc writes, no order routing. a test in `tests/test_safety.py` fails if the words for any of that appear in the package.
- no network calls. the package runs on synthetic pools. the only file it reads is the csv you pass with `--trades`, and it only reads it.
- the static site has no forms, no analytics and no third party requests. fonts are self hosted.

if you find a way the code could touch funds, a key or the network, or anything else that looks like a security issue, do not open a public issue. open a private report through github security advisories on this repo, or contact [@h100envy](https://github.com/h100envy). expect an answer within a few days.
