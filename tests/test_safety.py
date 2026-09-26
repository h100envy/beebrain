"""0.3 is paper only: no key handling or signing code in the package.
the pull request that adds live execution on purpose removes this test and adds its own checks."""
import os

PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "beebrain")
# split so this file does not match itself if someone widens the scan
FORBIDDEN = ["private" + " key", "seed" + " phrase", "send" + "Transaction", "sign" + "Transaction"]


def test_no_key_or_signing_words_in_the_package():
    hits = []
    for root, _, files in os.walk(PKG):
        for f in files:
            if f.startswith("._") or not f.endswith((".py", ".toml", ".cfg", ".txt", ".json", ".md")):
                continue
            path = os.path.join(root, f)
            text = open(path, encoding="utf-8").read().lower()
            for word in FORBIDDEN:
                if word.lower() in text:
                    hits.append("%s: %s" % (os.path.relpath(path, PKG), word))
    assert not hits, hits
