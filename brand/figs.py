"""
article figures, rendered with headless chromium into web/assets/article/.

  python brand/figs.py            all figures
  python brand/figs.py 06 07      only these

01 to 05 are drawn here. 02 and 03 sit on point cloud stills from render/stills.py, which
runs first if build/art/ is empty (needs numpy and scipy). 06 runs the engine for the ten
seeds, so the bars are whatever the sim returns. 07 is a terminal frame, 08 the robinhood
chain page from web/robinhood/.

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import json
import math
import os
import subprocess
import sys

from common import ART, ARTICLE_OUT, BUILD, ROOT, font_css, need_playwright, shoot

OUT = ARTICLE_OUT
os.makedirs(OUT, exist_ok=True)
if not os.path.exists(os.path.join(ART, "anchors.json")):
    subprocess.check_call([sys.executable, os.path.join(ROOT, "render", "stills.py")])
A = json.load(open(os.path.join(ART, "anchors.json")))

BASE = "<style>" + font_css().replace("%", "%%") + """
:root{--bg:#07080c;--text:#ecebf2;--dim:#7a7f92;--faint:#3a3f4d;--pink:#ff4fa3;--pinkh:#ffafd7;--violet:#9d7cff;
--lav:#8f84ff;--lime:#ccff3c;--green:#3fe08a;--red:#ff5468;--orange:#ffb04a;--line:#252a36}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#000;color:var(--text);font-family:'JetBrains Mono',monospace;width:%dpx;height:%dpx;overflow:hidden;position:relative}
.g{font-family:'Space Grotesk',sans-serif}
.t{position:absolute;left:72px;top:60px;font-family:'Space Grotesk';font-weight:700;font-size:46px;letter-spacing:-.5px;line-height:1.05}
.s{position:absolute;left:74px;top:122px;color:var(--dim);font-size:19px}
.src{position:absolute;left:74px;bottom:44px;color:var(--faint);font-size:15px}
.tag{position:absolute;right:72px;bottom:44px;color:var(--faint);font-size:15px}
</style>
"""


def page(w, h, body):
    return "<html><head><meta charset=utf-8>" + (BASE % (w, h)) + "</head><body>" + body + "</body></html>"


FIGS = {}

# ------------------------------------------------------------- fly vs bee
def dots(n_lit, color):
    out = []
    for i in range(100):
        r, c = divmod(i, 10)
        lit = i < n_lit
        glow = 'filter="url(#gl)"' if lit else ""
        out.append(f'<circle cx="{c*34+17}" cy="{r*34+17}" r="{11 if lit else 7}" fill="{color if lit else "#262a36"}" {glow}/>')
    return ('<svg width="340" height="340"><defs><filter id="gl"><feGaussianBlur stdDeviation="3" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>' + "".join(out) + "</svg>")

def species(x, name, neurons, kc, share, n_lit, col):
    return f"""
<div style="position:absolute;left:{x}px;top:230px;width:640px">
  <div class="g" style="font-size:34px;font-weight:700;color:{col}">{name}</div>
  <div style="display:flex;gap:44px;margin-top:26px;align-items:flex-start">
    {dots(n_lit, col)}
    <div style="width:250px">
      <div style="color:var(--dim);font-size:16px">neurons in the brain</div>
      <div class="g" style="font-size:40px;font-weight:700;margin:4px 0 20px">{neurons}</div>
      <div style="color:var(--dim);font-size:16px">kenyon cells per mushroom body</div>
      <div class="g" style="font-size:40px;font-weight:700;margin:4px 0 20px">{kc}</div>
      <div style="color:var(--dim);font-size:16px">share of the brain</div>
      <div class="g" style="font-size:40px;font-weight:700;color:{col};margin-top:4px">{share}</div>
    </div>
  </div>
</div>"""

FIGS["01-fly-vs-bee"] = (1600, 900, f"""
<div class="t">a fifth of the bee brain is built for one job</div>
<div class="s">linking what it senses to what happened next. each grid is a whole brain, lit dots are kenyon cells.</div>
{species(72, "fruit fly", "139,255", "~2,500", "~2%", 2, "#9d7cff")}
{species(840, "honeybee", "~960,000", "~175,000", "~20%", 20, "#ff4fa3")}
<div class="src">flywire 2024 · menzel and giurfa 2001 via bionumbers · campbell and turner 2010</div>
<div class="tag">beebrain · nerve</div>
""")

# ----------------------------------------------------------------- reward
def lab(x, y, text, sub, col, dx, dy, align="left"):
    lx, ly = x + dx, y + dy
    return f"""
<svg style="position:absolute;left:0;top:0" width="1600" height="900"><line x1="{x}" y1="{y}" x2="{lx}" y2="{ly}" stroke="{col}" stroke-width="1.5" opacity=".8"/>
<circle cx="{x}" cy="{y}" r="6" fill="none" stroke="{col}" stroke-width="2"/></svg>
<div style="position:absolute;{'left' if align=='left' else 'right'}:{lx+12 if align=='left' else 1600-lx+12}px;top:{ly-30}px;text-align:{align}">
<div style="font-weight:700;font-size:21px;color:{col}">{text}</div><div style="font-size:15px;color:var(--dim);margin-top:4px">{sub}</div></div>"""

cal, al, seg = A["r_calyx"], A["r_al"], A["r_seg"]
FIGS["03-reward-channels"] = (1600, 900, f"""
<img src="file://{ART}/brain_reward.png" style="position:absolute;left:0;top:0;width:1600px;height:900px">
<div class="t">one neuron carries the sugar</div>
<div class="s">in a bee, vummx1 broadcasts reward. in beebrain, a closed trade does.</div>
{lab(cal[0], cal[1], "mushroom body calyces", "memory: only cells that fired get updated", "#ccff3c", 170, -60)}
{lab(al[0], al[1], "antennal lobes", "input weighting shifts too", "#ccff3c", 230, 60)}
{lab(seg[0], seg[1], "vummx1 · subesophageal ganglion", "one cell, octopamine, the sugar signal", "#ccff3c", 240, 150)}
<div style="position:absolute;left:74px;top:640px;width:560px;font-size:18px;line-height:1.7">
<div><span style="color:var(--lime);font-weight:700">print</span> <span style="color:var(--dim)">→ sugar channel</span></div>
<div><span style="color:var(--red);font-weight:700">rug</span> <span style="color:var(--dim)">→ punishment channel, its own weight</span></div>
<div style="color:var(--faint);font-size:15px;margin-top:6px">unlike a bee, rug memory does not fade faster</div></div>
<div class="src" style="left:auto;right:72px">hammer 1993 · hammer and menzel 1998 · mizunami and matsumoto 2010</div>
""")

# ----------------------------------------------------------------- waggle
def fig8():
    # draw: straight run vertical with zigzag, two return loops
    run = "M300,190 " + " ".join(f"L{300 + (18 if i % 2 else -18)},{190 + i * 16}" for i in range(1, 20)) + " L300,510"
    loops = ('<path d="M300,510 C120,520 90,190 300,190" fill="none" stroke="#ff4fa3" stroke-width="3" opacity=".55"/>'
             '<path d="M300,510 C480,520 510,190 300,190" fill="none" stroke="#ff4fa3" stroke-width="3" opacity=".55"/>')
    return f"""<svg width="760" height="700" style="position:absolute;left:60px;top:170px">
{loops}<path d="{run}" fill="none" stroke="#ffafd7" stroke-width="3.5"/>
<circle cx="300" cy="190" r="10" fill="#f3efe6"/>
<line x1="560" y1="190" x2="560" y2="510" stroke="#7a7f92" stroke-width="1.5"/><line x1="552" y1="190" x2="568" y2="190" stroke="#7a7f92"/><line x1="552" y1="510" x2="568" y2="510" stroke="#7a7f92"/>
<text x="578" y="345" fill="#ecebf2" font-family="JetBrains Mono" font-size="18">run length</text><text x="578" y="370" fill="#7a7f92" font-family="JetBrains Mono" font-size="16">= score</text>
<line x1="282" y1="560" x2="318" y2="560" stroke="#7a7f92" stroke-width="1.5"/>
<text x="300" y="592" fill="#ecebf2" text-anchor="middle" font-family="JetBrains Mono" font-size="18">wiggle width</text><text x="300" y="616" fill="#7a7f92" text-anchor="middle" font-family="JetBrains Mono" font-size="16">= dissent between lobes</text>
</svg>"""

rows = [("mushroom", .81, "seen 14, printed 11", "#ff4fa3"), ("antennal", .38, "noisy input", "#8f84ff"),
        ("optic", .87, "narrative accelerating", "#9d7cff"), ("central", .72, "exploit", "#c4a8ff")]
vec = "".join(f"""<div style="display:flex;align-items:center;gap:18px;margin-bottom:26px">
<div style="width:120px;font-size:20px">{n}</div><div style="width:300px;height:12px;background:#1d212c;border-radius:6px;overflow:hidden">
<div style="width:{v*100}%;height:100%;background:{c}"></div></div><div class="g" style="width:60px;font-size:24px;font-weight:700">{v:.2f}</div>
<div style="color:var(--dim);font-size:17px">{s}</div></div>""" for n, v, s, c in rows)
FIGS["04-waggle-vector"] = (1600, 900, f"""
<div class="t">the output is a vector, not a number</div>
<div class="s">a forager's dance carries direction, distance and quality. beebrain's carries one value per lobe.</div>
{fig8()}
<div style="position:absolute;left:760px;top:250px">{vec}
<div style="display:flex;align-items:center;gap:18px;margin-top:10px"><div style="width:120px;font-size:20px">motor</div>
<div class="g" style="font-size:40px;font-weight:700;color:var(--green)">PASS</div><div style="color:var(--orange);font-size:17px">flag: antennal below 0.50</div></div>
<div style="color:var(--faint);font-size:15px;margin-top:24px">example values. a single 0.73 would hide all of this.</div></div>
<div class="src">von frisch, nobel 1973 · nature review of his work · nc state extension</div>
""")

# ------------------------------------------------------------------ lobes
L = [("optic lobes", "narrative shape from the grok map", "#9d7cff", 70, -95),
     ("mushroom bodies", "memory: 2,000 kenyon cells, 5% fire per pool", "#ff4fa3", -250, -20),
     ("central complex", "ring attractor, explore or exploit", "#c4a8ff", -330, 30),
     ("antennal lobes", "8 glomeruli, one per feature, measures noise", "#8f84ff", 200, 170),
     ("subesophageal ganglion", "verdict and the reward broadcast", "#ff5468", -330, 110)]
lb = ""
for name, sub, col, dx, dy in L:
    x, y = A[name]
    lb += lab(x, y, name, sub, col, dx, dy, "left" if dx > 0 else "right")
FIGS["02-lobes"] = (1600, 900, f"""
<img src="file://{ART}/brain_lobes.png" style="position:absolute;left:0;top:0;width:1600px;height:900px">
<div class="t">five lobes, five jobs on the desk</div>
<div class="s">schematic point cloud laid out from bee brain anatomy. 72,600 points drawn.</div>
{lb}
<div class="tag">beebrain · nerve</div>
""")

# --------------------------------------------------------------- pipeline
def box(x, y, w, h, title, sub, col, fill="#10121a"):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" stroke="{col}" stroke-width="1.5"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="30" rx="6" fill="{col}"/><rect x="{x}" y="{y+20}" width="{w}" height="10" fill="{col}"/>'
            f'<text x="{x+14}" y="{y+21}" font-family="JetBrains Mono" font-weight="700" font-size="15" fill="#0b0c10">{title}</text>'
            + "".join(f'<text x="{x+14}" y="{y+56+i*22}" font-family="JetBrains Mono" font-size="14" fill="#9aa0b2">{s}</text>' for i, s in enumerate(sub)))

def arrow(x1, y1, x2, y2, col="#3a3f4d", dash=""):
    mx = (x1 + x2) / 2
    return (f'<path d="M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}" fill="none" stroke="{col}" stroke-width="2" {dash} marker-end="url(#ah)"/>')

svg = ['<svg width="1600" height="700" style="position:absolute;left:0;top:170px"><defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#5a6072"/></marker></defs>']
svg.append(box(60, 250, 190, 110, "scanner", ["new pools on", "solana, robinhood,", "base"], "#2e3342"))
svg.append(box(300, 250, 200, 110, "reflex + sentinel", ["bundle, snipers,", "bump ratio,", "eth_call sell sim"], "#c9364f"))
svg.append('<rect x="560" y="60" width="560" height="500" rx="10" fill="rgba(255,79,163,.04)" stroke="#ff4fa3" stroke-dasharray="6 6"/>'
           '<text x="580" y="92" font-family="Space Grotesk" font-weight="700" font-size="24" fill="#ff4fa3">beebrain</text>')
svg.append(box(590, 250, 150, 110, "antennal", ["8 features", "input noise"], "#8f84ff"))
svg.append(box(780, 130, 150, 100, "optic", ["narrative", "shape"], "#9d7cff"))
svg.append(box(780, 380, 150, 100, "mushroom", ["sparse code", "memory"], "#ff4fa3"))
svg.append(box(960, 250, 140, 110, "central", ["explore or", "exploit"], "#6d63d6"))
svg.append(box(1170, 250, 160, 110, "motor", ["waggle vector", "PASS WATCH SKIP"], "#ff5468"))
svg.append(box(1380, 140, 200, 100, "jev · grok · opus", ["read the", "vector"], "#2e3342"))
svg.append(box(1380, 370, 200, 100, "you", ["click or", "skip"], "#ffb04a"))
for a in [(250, 305, 300, 305), (500, 305, 590, 305), (740, 290, 780, 180), (740, 320, 780, 430), (930, 180, 960, 290),
          (930, 430, 960, 320), (855, 230, 855, 380), (1100, 305, 1170, 305), (1330, 290, 1380, 190), (1330, 320, 1380, 420)]:
    svg.append(arrow(*a))
svg.append('<path d="M1475,470 C1475,640 900,660 855,480" fill="none" stroke="#ccff3c" stroke-width="2.5" marker-end="url(#ah)"/>'
           '<path d="M1440,470 C1400,600 700,640 665,360" fill="none" stroke="#ccff3c" stroke-width="1.5" opacity=".5" marker-end="url(#ah)"/>'
           '<text x="1080" y="640" font-family="JetBrains Mono" font-size="17" fill="#ccff3c">trade closes: print = sugar, rug = punishment</text>')
svg.append("</svg>")
FIGS["05-pipeline"] = (1600, 900, f"""
<div class="t">where the bee sits in nerve</div>
<div class="s">after the reflexes, before the models. the result of every trade flows back into memory.</div>
{''.join(svg)}
<div class="tag">beebrain · nerve</div>
""")

# ------------------------------------------------------------------ seeds
sys.path.insert(0, ROOT)
from beebrain.engine import run  # noqa: E402

runs = [run(s, 9, record=False).summary() for s in range(10)]
seeds = sorted(((r["seed"], round(r["final"]), r["trades"], round(100 * r["win_rate"])) for r in runs),
               key=lambda x: -x[1])
mx = max(7200, math.ceil(seeds[0][1] / 400) * 400 + 400)
bars = ""
for i, (s, v, n, wr) in enumerate(seeds):
    y = 220 + i * 56
    w = v / mx * 900
    col = "#ccff3c" if v >= 500 else "#ff5468"
    bars += (f'<div style="position:absolute;left:74px;top:{y}px;width:120px;font-size:18px;color:var(--dim)">seed {s}</div>'
             f'<div style="position:absolute;left:200px;top:{y+2}px;height:26px;width:{w}px;background:{col};opacity:{1 if v>=1000 else .75};border-radius:2px"></div>'
             f'<div class="g" style="position:absolute;left:{214+w}px;top:{y-2}px;font-size:24px;font-weight:700">${v:,}</div>'
             f'<div style="position:absolute;left:{330+w}px;top:{y+3}px;font-size:16px;color:var(--dim)">{n} trades · {wr}% wins</div>')
x500 = 200 + 500 / mx * 900
FIGS["06-solana-seeds"] = (1600, 900, f"""
<div class="t">ten seeds, one brain, nine days</div>
<div class="s">paper account from $500 on synthetic solana pools, fees in. same settings every run.</div>
{bars}
<div style="position:absolute;left:{x500}px;top:205px;width:2px;height:570px;background:#ecebf2;opacity:.35"></div>
<div style="position:absolute;left:{x500+8}px;top:786px;font-size:15px;color:var(--dim)">$500 start</div>
<div style="position:absolute;left:1180px;top:640px;width:360px;font-size:16px;line-height:1.6;color:var(--dim)">the edge in these pools was planted: creator age, sniper share, bundles. the run shows the brain can find an edge that exists, not that it exists on a real chain.</div>
<div class="tag">beebrain · nerve · simulation</div>
""")


def terminal_still():
    """07: one frame of the stage 1 terminal after a few simulated hours"""
    from termshot import canvas_html
    from beebrain.terminal.app import frame, make_show
    s = make_show(1, 5, 1.0)
    for _ in range(20 * 120):          # 120 pools at the default speed
        s.step()
    html, w, h = canvas_html(frame(1, "wide", s, 176, 50), font_px=15)
    return html, w, h


def robinhood_still(out, at_ms=16000):
    """08: the robinhood chain node graph page, part way into its run"""
    need_playwright()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 900})
        pg.goto("file://" + os.path.join(ROOT, "web", "robinhood", "index.html"))
        pg.wait_for_timeout(at_ms)
        pg.screenshot(path=out)
        b.close()
    print("wrote", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    want = sys.argv[1:]
    pages = []
    for name, (w, h, body) in FIGS.items():
        if not want or name[:2] in want:
            pages.append((page(w, h, body), w, h, os.path.join(OUT, name + ".png")))
    if not want or "07" in want:
        html, w, h = terminal_still()
        pages.append((html, w, h, os.path.join(OUT, "07-terminal-solana.png")))
    shoot(pages)
    if not want or "08" in want:
        robinhood_still(os.path.join(OUT, "08-robinhood-first-contact.png"))
    os.makedirs(BUILD, exist_ok=True)
