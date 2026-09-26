"""
terminal frames as html, for stills and the readme gif. reads the canvas the terminal
already draws, so every number in the picture comes from the running engine.

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import html
import re

import os

from common import ROOT, font_css

FULL = "@font-face{font-family:'JBM Full';font-weight:100 800;src:url('file://%s')}" % os.path.join(ROOT, "brand", "fonts", "JetBrainsMono.ttf")

SGR = re.compile(r"\x1b\[([0-9;]*)m")


def xterm(n):
    """xterm 256 colour index to hex"""
    base = ["000000", "800000", "008000", "808000", "000080", "800080", "008080", "c0c0c0",
            "808080", "ff0000", "00ff00", "ffff00", "0000ff", "ff00ff", "00ffff", "ffffff"]
    if n < 16:
        return "#" + base[n]
    if n < 232:
        n -= 16
        steps = [0, 95, 135, 175, 215, 255]
        return "#%02x%02x%02x" % (steps[n // 36], steps[(n // 6) % 6], steps[n % 6])
    v = 8 + (n - 232) * 10
    return "#%02x%02x%02x" % (v, v, v)


def style(codes):
    fg, bg, bold = None, None, False
    parts = [c for c in codes.split(";") if c != ""]
    i = 0
    while i < len(parts):
        c = parts[i]
        if c == "0":
            fg, bg, bold = None, None, False
        elif c == "1":
            bold = True
        elif c in ("38", "48") and i + 2 < len(parts) and parts[i + 1] == "5":
            if c == "38":
                fg = xterm(int(parts[i + 2]))
            else:
                bg = xterm(int(parts[i + 2]))
            i += 2
        i += 1
    return fg, bg, bold


def canvas_html(cv, font_px=14, pad=18):
    """one canvas frame to a standalone html page. returns (html, width_px, height_px)."""
    base_bg = style(cv.bg[2:-1])[1] or "#000000"
    rows = []
    for y in range(cv.h):
        out, run, cur = [], [], None
        for x in range(cv.w):
            fg, bg, bold = style(cv.co[y][x].replace("\x1b[", "").replace("m", ";")) if cv.co[y][x] else (None, None, False)
            key = (fg, bg, bold)
            if key != cur and run:
                out.append(span(cur, "".join(run)))
                run = []
            cur = key
            run.append(cv.ch[y][x])
        if run:
            out.append(span(cur, "".join(run)))
        rows.append("".join(out))
    cw, lh = font_px * 0.6, round(font_px * 1.18)
    w = int(cv.w * cw + pad * 2)
    h = int(cv.h * lh + pad * 2)
    page = ("<html><head><meta charset=utf-8><style>%s*{margin:0;padding:0}"
            "body{background:%s;width:%dpx;height:%dpx;overflow:hidden}"
            "pre{font-family:'JBM Full',Menlo,monospace;font-size:%dpx;line-height:%dpx;color:#bcbcbc;"
            "padding:%dpx;white-space:pre;font-variant-ligatures:none}b{font-weight:700}</style></head>"
            "<body><pre>%s</pre></body></html>") % (font_css() + FULL, base_bg, w, h, font_px, lh, pad, "\n".join(rows))
    return page, w, h


def span(key, text):
    fg, bg, bold = key
    text = html.escape(text)
    css = []
    if fg:
        css.append("color:" + fg)
    if bg:
        css.append("background:" + bg)
    if not css and not bold:
        return text
    tag = "b" if bold else "span"
    return "<%s style=\"%s\">%s</%s>" % (tag, ";".join(css), text, tag)
