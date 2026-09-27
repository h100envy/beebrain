"""
svg art for the readme: the roadmap strip. plain svg, renders on github without fonts or scripts.
python brand/readme_art.py writes docs/media/roadmap.svg
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = 'font-family="JetBrains Mono, Menlo, Consolas, monospace"'
PHASES = [
    ("the sim", "done", "#ff4fa3", ["five lobes, planted edge", "10 seeds, tests pin it"]),
    ("the field", "live now", "#3fe08a", ["real pools, paper money", "race you and random"]),
    ("signals", "next", "#ffb04a", ["pass alerts, telegram, api", "read only wallet scoring"]),
    ("the gate", "when earned", "#9d7cff", ["300 pools, PASS beats SKIP", "bee beats random"]),
    ("execution", "after the gate", "#c4a8ff", ["opt in, your own wallet", "small size, hard limits"]),
]


def roadmap(W=1200, H=250, x0=130):
    step = (W - 2 * x0) / (len(PHASES) - 1)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<defs><linearGradient id="l" gradientUnits="userSpaceOnUse" x1="{x0}" y1="0" x2="{W - x0}" y2="0">'
         '<stop offset="0" stop-color="#ff4fa3"/><stop offset=".25" stop-color="#3fe08a"/>'
         '<stop offset=".5" stop-color="#ffb04a"/><stop offset="1" stop-color="#c4a8ff"/></linearGradient>'
         '<filter id="g" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="8"/></filter></defs>',
         f'<rect width="{W}" height="{H}" rx="16" fill="#07060a"/>',
         f'<line x1="{x0}" y1="92" x2="{W - x0}" y2="92" stroke="url(#l)" stroke-width="3" opacity=".8"/>']
    for i, (name, state, c, lines) in enumerate(PHASES):
        x = x0 + i * step
        o.append(f'<circle cx="{x:.0f}" cy="92" r="20" fill="{c}" opacity=".45" filter="url(#g)"/>')
        o.append(f'<circle cx="{x:.0f}" cy="92" r="11" fill="{c if i < 2 else "#07060a"}" stroke="{c}" stroke-width="3"/>')
        if state == "live now":
            o.append(f'<circle cx="{x:.0f}" cy="92" r="11" fill="none" stroke="{c}" stroke-width="2">'
                     '<animate attributeName="r" values="11;26;11" dur="2.4s" repeatCount="indefinite"/>'
                     '<animate attributeName="opacity" values="1;0;1" dur="2.4s" repeatCount="indefinite"/></circle>')
        o.append(f'<text x="{x:.0f}" y="46" text-anchor="middle" {F} font-size="13" fill="{c}" letter-spacing="2">{state.upper()}</text>')
        o.append(f'<text x="{x:.0f}" y="148" text-anchor="middle" {F} font-size="20" font-weight="700" fill="#f3efe6">{name}</text>')
        for j, line in enumerate(lines):
            o.append(f'<text x="{x:.0f}" y="{176 + j * 22}" text-anchor="middle" {F} font-size="13" fill="#a09caa">{line}</text>')
    o.append("</svg>")
    return "\n".join(o)


if __name__ == "__main__":
    path = os.path.join(ROOT, "docs", "media", "roadmap.svg")
    with open(path, "w") as fh:
        fh.write(roadmap())
    print("wrote docs/media/roadmap.svg")
