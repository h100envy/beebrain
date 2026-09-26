"""
shared bits for the brand scripts: repo paths, self hosted fonts for headless chromium,
and a screenshot helper. playwright is an optional extra: pip install -e '.[figures]'

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "web", "assets", "fonts")
BUILD = os.path.join(ROOT, "build")
ART = os.path.join(BUILD, "art")
BRAND_OUT = os.path.join(ROOT, "web", "assets", "brand")
ARTICLE_OUT = os.path.join(ROOT, "web", "assets", "article")

sys.path.insert(0, ROOT)          # so `import beebrain` works from a plain clone


def font_css():
    """@font-face rules pointing at the self hosted woff2 files, for pages rendered from disk"""
    url = "file://" + FONTS
    return (
        "@font-face{font-family:'Cinzel';font-weight:400 900;src:url('%s/cinzel-latin.woff2') format('woff2')}"
        "@font-face{font-family:'Space Grotesk';font-weight:300 700;src:url('%s/spacegrotesk-latin.woff2') format('woff2')}"
        "@font-face{font-family:'JetBrains Mono';font-weight:100 800;src:url('%s/jetbrainsmono-latin.woff2') format('woff2')}"
    ) % (url, url, url)


def need_playwright():
    try:
        import playwright  # noqa: F401
    except ImportError:
        sys.stderr.write("this script needs playwright: pip install -e '.[figures]' "
                         "and python -m playwright install chromium\n")
        raise SystemExit(2)


def shoot(pages, wait=500):
    """pages: list of (html, width, height, out_png). renders each from a temp file so file:// fonts load."""
    need_playwright()
    from playwright.sync_api import sync_playwright
    tmp = os.path.join(BUILD, "html")
    os.makedirs(tmp, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for i, (html, w, h, out) in enumerate(pages):
            path = os.path.join(tmp, "page_%03d.html" % i)
            with open(path, "w") as fh:
                fh.write(html)
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg.goto("file://" + path)
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(wait)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            pg.screenshot(path=out)
            pg.close()
            print("wrote", os.path.relpath(out, ROOT))
        b.close()
