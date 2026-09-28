"""one source for the token ticker and address in the site, readme and videos."""
import argparse
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "token-settings.json"
CHAINS = ("solana", "base", "bsc", "ethereum", "robinhood")


def validate(config):
    ticker = config.get("ticker", "")
    ca = config.get("contract", "")
    chain = config.get("chain", "")
    if not isinstance(ticker, str) or not re.fullmatch(r"[A-Z0-9]{2,16}", ticker):
        raise ValueError("ticker must contain 2 to 16 uppercase letters or digits, without $")
    if not isinstance(chain, str) or (chain and chain not in CHAINS):
        raise ValueError("unknown chain")
    if not isinstance(ca, str):
        raise ValueError("contract must be a string")
    if ca:
        if not chain:
            raise ValueError("set --chain together with the contract address")
        pattern = r"[1-9A-HJ-NP-Za-km-z]{32,44}" if chain == "solana" else r"0x[0-9a-fA-F]{40}"
        if not re.fullmatch(pattern, ca):
            raise ValueError("contract format does not match the chain; paste the complete address without spaces")
    return {"ticker": ticker, "chain": chain, "contract": ca}


def load_config(path=CONFIG):
    return validate(json.loads(Path(path).read_text(encoding="utf-8")))


def token_html(config):
    config = validate(config)
    ticker, ca, chain = (html.escape(config[k]) for k in ("ticker", "contract", "chain"))
    return ('<div class="token-card" aria-label="token contract">\n'
            '  <div class="token-heading"><strong>$%s</strong><span>%s</span></div>\n'
            '  <div class="token-contract"><span>CA:</span><code id="token-address">%s</code>\n'
            '    <button class="btn" id="copy-token-ca" type="button"%s>copy CA</button></div>\n'
            '  <p class="token-feedback" id="token-feedback" role="status">%s</p>\n'
            '</div>' % (ticker, chain or "contract not announced", ca or "not announced", "" if ca else " disabled",
                        "" if ca else "the address will appear here after launch."))


def token_markdown(config):
    config = validate(config)
    lines = ["## token", "", "**ticker:** `$%s`" % config["ticker"]]
    if config["chain"]:
        lines += ["", "**network:** %s" % config["chain"]]
    lines += ["", "**CA:** " + ("`%s`" % config["contract"] if config["contract"] else "not announced. the address will be added after launch.")]
    return "\n".join(lines)


def overlay_text(config):
    config = validate(config)
    return "$%s%s   CA: %s" % (config["ticker"], " / " + config["chain"] if config["chain"] else "", config["contract"])


def render_video(config, font=None):
    """fit the original inside the frame; reserve the bottom strip for CA."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("ffmpeg is required for --video")
    candidates = [Path(font)] if font else [Path("/System/Library/Fonts/Menlo.ttc"),
                                           Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")]
    font_path = next((p for p in candidates if p.is_file()), None)
    if font_path is None:
        raise ValueError("choose a local monospace font with --font")
    source = ROOT / "build/beebrain-3d.mp4"
    if not source.is_file():
        source = ROOT / "web/assets/video/beebrain-3d-1080.mp4"
    outdir = ROOT / "build/token-launch"
    outdir.mkdir(parents=True, exist_ok=True)
    # simple relative filter paths keep spaces and punctuation out of ffmpeg's filter parser
    shutil.copyfile(font_path, outdir / "overlay-font.ttf")
    (outdir / "overlay.txt").write_text(overlay_text(config), encoding="utf-8")
    output_dir = ROOT / "videos-with-ca"
    output_dir.mkdir(exist_ok=True)
    name = "beebrain-3d-ca.mp4" if config["contract"] else "beebrain-3d-ca-preview.mp4"
    vf = ("scale=1760:990,pad=1920:1080:80:0:black,"
          "drawbox=x=80:y=999:w=1760:h=1:color=0x653048:t=fill,"
          "drawtext=fontfile=overlay-font.ttf:textfile=overlay.txt:expansion=none:"
          "fontcolor=0xffafd7:fontsize=27:x=(w-text_w)/2:y=1025")
    subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(source), "-vf", vf, "-c:v", "libx264",
                    "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy",
                    "-movflags", "+faststart", str(output_dir / name)], cwd=outdir, check=True)
    print("wrote", output_dir / name)


def render_morph(config):
    renderer = ROOT / "brand/promo/morph/render.py"
    if not renderer.is_file():
        print("morph renderer not present; 3d video is ready")
        return
    name = "beebrain-morph-ca.mp4" if config["contract"] else "beebrain-morph-ca-preview.mp4"
    env = dict(os.environ)
    if Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").is_file():
        env.setdefault("BEEBRAIN_RENDER_BROWSER", "chrome")
    subprocess.run([sys.executable, str(renderer), str(ROOT / "videos-with-ca" / name)], cwd=ROOT, env=env, check=True)


def sync_promos(config):
    # existing editable promo templates can consume the same address immediately
    morph = ROOT / "brand/promo/morph"
    if morph.is_dir():
        (morph / "token.js").write_text("const TOKEN = " + json.dumps(config) + ";\n", encoding="utf-8")
    launch = ROOT / "brand/promo/launch"
    if launch.is_dir():
        (launch / "settings.js").write_text("const LAUNCH_CA = " + json.dumps(config["contract"]) + ";\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ticker")
    ap.add_argument("--ca", help="full contract address; no transaction is performed")
    ap.add_argument("--chain", choices=CHAINS)
    ap.add_argument("--video", action="store_true", help="also export the 3d video with ticker and CA")
    ap.add_argument("--visuals-only", action="store_true", help="export videos first; leave homepage and README unchanged")
    ap.add_argument("--font", help="monospace font file for the video")
    args = ap.parse_args(argv)
    config = load_config()
    for key, value in (("ticker", args.ticker), ("contract", args.ca), ("chain", args.chain)):
        if value is not None:
            config[key] = value
    try:
        config = validate(config)
    except ValueError as e:
        ap.error(str(e))
    CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    sync_promos(config)
    if args.video or args.visuals_only:
        render_morph(config)
        render_video(config, args.font)
    if not args.visuals_only:
        subprocess.run([sys.executable, str(ROOT / "web/build.py")], cwd=ROOT, check=True)
    print("local assets updated; nothing published")


if __name__ == "__main__":
    main()
