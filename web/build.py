"""
builds the static site. stdlib only, no framework.

  python web/build.py                   render docs/article.md to web/article/index.html and refresh
                                        the computed blocks in web/index.html and README.md
  python web/build.py --check           build into memory, fail if a committed file is stale,
                                        a local link is broken or an image has no alt text
  python web/build.py --domain example.com
                                        replace the BEEBRAIN_DOMAIN placeholder in the site

computed blocks sit between <!-- sim:NAME --> and <!-- /sim:NAME --> markers. they are filled
from a headless engine run, so no number on the site is typed by hand.

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import argparse
import html
import json
import os
import re
import sys

WEB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(WEB)
sys.path.insert(0, ROOT)

from beebrain.brain import waggle_vector  # noqa: E402
from beebrain.engine import Engine, run  # noqa: E402

PLACEHOLDER = "BEEBRAIN_DOMAIN"
SEEDS = range(10)
DAYS = 9
VECTOR_SEED, VECTOR_POOL = 5, 120


# ------------------------------------------------------------ markdown ---
def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", lambda m: "<code>%s</code>" % m.group(1), s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: '<img src="%s" alt="%s" loading="lazy">' % (m.group(2), m.group(1)), s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: '<a href="%s">%s</a>' % (m.group(2), m.group(1)), s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\s][^*]*)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def markdown(md):
    """the subset the article uses: headings, paragraphs, lists, tables, images, code"""
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre><code>%s</code></pre>" % html.escape("\n".join(lines[i + 1:j])))
            i = j + 1
            continue
        m = re.match(r"(#{1,6}) (.*)", ln)
        if m:
            n, text = len(m.group(1)), m.group(2).strip()
            out.append('<h%d id="%s">%s</h%d>' % (n, slug(text), inline(text), n))
            i += 1
            continue
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows, j = [], i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip().strip("|").split("|")])
                j += 1
            t = ['<div class="table"><table><thead><tr>%s</tr></thead><tbody>' % "".join('<th scope="col">%s</th>' % inline(c) for c in head)]
            for r in rows:
                t.append("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r))
            t.append("</tbody></table></div>")
            out.append("".join(t))
            i = j
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.) (.*)", ln)
        if m:
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            items, j = [], i
            while j < len(lines):
                mm = re.match(r"^(\s*)([-*]|\d+\.) (.*)", lines[j])
                if not mm:
                    break
                items.append(mm.group(3))
                j += 1
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(x) for x in items), tag))
            i = j
            continue
        if re.match(r"^!\[[^\]]*\]\([^)]+\)$", ln.strip()):
            m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", ln.strip())
            out.append('<figure><img src="%s" alt="%s" loading="lazy"><figcaption>%s</figcaption></figure>'
                       % (m.group(2), html.escape(m.group(1)), inline(m.group(1))))
            i += 1
            continue
        para = [ln]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||```|\s*([-*]|\d+\.) |!\[)", lines[i]):
            para.append(lines[i])
            i += 1
        out.append("<p>%s</p>" % inline(" ".join(p.strip() for p in para)))
    return "\n".join(out)


# ------------------------------------------------------------ computed ---
def seed_rows():
    return [run(s, DAYS, record=False).summary() for s in SEEDS]


def seeds_html(rows):
    body = []
    for r in sorted(rows, key=lambda r: -r["final"]):
        up = "up" if r["final"] >= r["start"] else "down"
        body.append('<tr class="%s"><td>seed %d</td><td>${:,.0f}</td><td>%d</td><td>%.0f%%</td><td>%.0f%%</td></tr>'.format(r["final"])
                    % (up, r["seed"], r["trades"], r["win_rate"] * 100, r["max_drawdown"] * 100))
    return ('<div class="table"><table><caption>paper account from $500, nine days of 40 synthetic pools, fees in. '
            'computed by <code>beebrain sim --seeds 0-9</code> when this page was built.</caption>'
            '<thead><tr><th scope="col">run</th><th scope="col">final</th><th scope="col">trades</th>'
            '<th scope="col">wins</th><th scope="col">max drawdown</th></tr></thead><tbody>'
            + "".join(body) + "</tbody></table></div>")


def seeds_md(rows):
    out = ["| seed | final | trades | win rate | max drawdown |", "| --- | --- | --- | --- | --- |"]
    for r in sorted(rows, key=lambda r: -r["final"]):
        out.append("| %d | ${:,.0f} | %d | %.0f%% | %.0f%% |".format(r["final"]) % (
            r["seed"], r["trades"], r["win_rate"] * 100, r["max_drawdown"] * 100))
    return "\n".join(out)


def vector_json():
    e = Engine(VECTOR_SEED)
    for _ in range(VECTOR_POOL):
        e.step()
    return json.dumps(waggle_vector(e.pool, e.thought), indent=2)


def fill(text, name, content):
    pat = re.compile(r"(<!-- sim:%s -->)(.*?)(<!-- /sim:%s -->)" % (name, name), re.S)
    if not pat.search(text):
        raise SystemExit("marker sim:%s missing" % name)
    return pat.sub(lambda m: m.group(1) + "\n" + content + "\n" + m.group(3), text)


# ---------------------------------------------------------------- pages ---
ARTICLE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>the article · BeeBrain · NERVE</title>
<meta name="description" content="a honeybee brain, simulated, scoring memecoin pools inside nerve">
<meta name="theme-color" content="#000000">
<link rel="canonical" href="https://BEEBRAIN_DOMAIN/article/">
<meta property="og:type" content="article">
<meta property="og:site_name" content="BeeBrain">
<meta property="og:title" content="BeeBrain · NERVE">
<meta property="og:description" content="a honeybee brain, simulated, scoring memecoin pools inside nerve">
<meta property="og:url" content="https://BEEBRAIN_DOMAIN/article/">
<meta property="og:image" content="https://BEEBRAIN_DOMAIN/assets/brand/cover.png">
<meta property="og:image:width" content="1500">
<meta property="og:image:height" content="600">
<meta property="og:image:alt" content="a honeycomb brain with the BeeBrain wordmark">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@beebrainnerve">
<meta name="twitter:title" content="BeeBrain · NERVE">
<meta name="twitter:description" content="a honeybee brain, simulated, scoring memecoin pools inside nerve">
<meta name="twitter:image" content="https://BEEBRAIN_DOMAIN/assets/brand/cover.png">
<link rel="icon" href="../assets/brand/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="../assets/brand/favicon-32.png">
<link rel="apple-touch-icon" href="../assets/brand/apple-touch-icon.png">
<link rel="preload" href="../assets/fonts/jetbrainsmono-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="../assets/fonts/fonts.css">
<link rel="stylesheet" href="../assets/site.css">
</head>
<body class="article">
<a class="skip" href="#main">skip to the article</a>
<header class="bar">
  <a class="mark" href="../">BeeBrain</a>
  <nav aria-label="site">
    <a href="../#how">how it works</a>
    <a href="../robinhood/">robinhood chain</a>
    <a href="https://github.com/h100envy/beebrain">github</a>
  </nav>
</header>
<main id="main">
<p class="sim-tag">sim · synthetic pools · paper account</p>
<article class="prose">
"""

ARTICLE_FOOT = """
</article>
</main>
<footer class="foot">
  <p>beebrain is research and visualisation. synthetic pools, paper account. no keys, no signatures, no orders.</p>
  <p><a href="https://github.com/h100envy/beebrain">github.com/h100envy/beebrain</a>
     · built on <a href="https://github.com/h100envy/nerve">nerve</a> · mit license
     · <a href="https://x.com/beebrainnerve">@beebrainnerve on x</a></p>
</footer>
</body>
</html>
"""


def article_html():
    md = open(os.path.join(ROOT, "docs", "article.md"), encoding="utf-8").read()
    md = md.replace("../web/assets/", "../assets/")
    return ARTICLE_HEAD + markdown(md) + ARTICLE_FOOT


def outputs():
    rows = seed_rows()
    vec = vector_json()
    idx_path = os.path.join(WEB, "index.html")
    readme_path = os.path.join(ROOT, "README.md")
    idx = open(idx_path, encoding="utf-8").read()
    idx = fill(idx, "seeds", seeds_html(rows))
    idx = fill(idx, "vector", "<pre><code>%s</code></pre>" % html.escape(vec))
    readme = open(readme_path, encoding="utf-8").read()
    readme = fill(readme, "vector", "```json\n%s\n```" % vec)
    readme = fill(readme, "seeds", seeds_md(rows))
    return {os.path.join(WEB, "article", "index.html"): article_html(), idx_path: idx, readme_path: readme}


# ---------------------------------------------------------------- check ---
def local_refs(path, text):
    refs = re.findall(r'(?:src|href|poster)="([^"]+)"', text) if path.endswith(".html") else \
        re.findall(r"\]\(([^)\s]+)\)|<img[^>]*src=\"([^\"]+)\"", text)
    for r in refs:
        r = r if isinstance(r, str) else (r[0] or r[1])
        if not r or re.match(r"^(https?:|mailto:|#|data:)", r):
            continue
        yield r.split("#")[0].split("?")[0]


def check(files):
    bad = []
    for path, text in files.items():
        base = os.path.dirname(path)
        for r in local_refs(path, text):
            target = os.path.normpath(os.path.join(base, r))
            if r.startswith("/"):
                target = os.path.join(WEB, r.lstrip("/"))
            if os.path.isdir(target):
                target = os.path.join(target, "index.html")
            if not os.path.exists(target):
                bad.append("%s: broken link %s" % (os.path.relpath(path, ROOT), r))
        for img in re.findall(r"<img\b[^>]*>", text):
            if not re.search(r'\balt="[^"]+"', img):
                bad.append("%s: image without alt text %s" % (os.path.relpath(path, ROOT), img[:80]))
        for img in re.findall(r"!\[([^\]]*)\]\(", text):
            if not img.strip():
                bad.append("%s: markdown image without alt text" % os.path.relpath(path, ROOT))
        if "—" in text:
            bad.append("%s: em dash" % os.path.relpath(path, ROOT))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--domain", default="")
    a = ap.parse_args()
    if a.domain:
        dom = re.sub(r"^https?://", "", a.domain).strip("/")
        for dirpath, _, fnames in os.walk(WEB):
            for f in fnames:
                if f.endswith((".html", ".xml", ".txt")) and not f.startswith("._"):
                    p = os.path.join(dirpath, f)
                    s = open(p, encoding="utf-8").read()
                    if PLACEHOLDER in s:
                        open(p, "w", encoding="utf-8").write(s.replace(PLACEHOLDER, dom))
                        print("domain set in", os.path.relpath(p, ROOT))
        return 0
    files = outputs()
    extra = {}
    for dirpath, _, fnames in os.walk(WEB):
        for f in fnames:
            p = os.path.join(dirpath, f)
            if f.endswith(".html") and not f.startswith("._") and p not in files:
                extra[p] = open(p, encoding="utf-8").read()
    problems = []
    if a.check:
        for path, text in files.items():
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
                problems.append("%s is stale, run python web/build.py" % os.path.relpath(path, ROOT))
    else:
        for path, text in files.items():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            print("wrote", os.path.relpath(path, ROOT))
    problems += check({**files, **extra})
    for p in problems:
        print("problem:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
