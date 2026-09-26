"""
records the readme gif: `beebrain terminal --layout wide --speed 3 --seed 5`, about 12 seconds.
frames come from the same canvas the terminal draws, rendered by headless chromium, then
ffmpeg builds an optimised gif with its own palette.

  python brand/record_gif.py [--seconds 12] [--fps 10] [--width 1100] [--out web/assets/brand/terminal.gif]

needs playwright and ffmpeg. idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import argparse
import os
import shutil
import subprocess

from common import BUILD, ROOT, need_playwright
from termshot import canvas_html

from beebrain.terminal.app import FPS, frame, make_show


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=12)
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--width", type=int, default=1100)
    ap.add_argument("--warm", type=int, default=600, help="terminal frames to run before recording")
    ap.add_argument("--out", default=os.path.join(ROOT, "web", "assets", "brand", "terminal.gif"))
    a = ap.parse_args()
    need_playwright()
    if not shutil.which("ffmpeg"):
        raise SystemExit("needs ffmpeg on the path")
    from playwright.sync_api import sync_playwright

    s = make_show(1, 5, 3.0)
    for _ in range(a.warm):
        s.step()
    frames_dir = os.path.join(BUILD, "gif")
    shutil.rmtree(frames_dir, ignore_errors=True)
    os.makedirs(frames_dir)
    n = int(a.seconds * FPS)                 # the terminal ticks at FPS
    keep_every = max(1, round(FPS / a.fps))
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = None
        k = 0
        for i in range(n):
            s.step()
            if i % keep_every:
                continue
            html, w, h = canvas_html(frame(1, "wide", s, 176, 50), font_px=14)
            if pg is None:
                pg = b.new_page(viewport={"width": w, "height": h})
            path = os.path.join(frames_dir, "f.html")
            with open(path, "w") as fh:
                fh.write(html)
            pg.goto("file://" + path)
            pg.evaluate("document.fonts.ready")
            pg.screenshot(path=os.path.join(frames_dir, "f_%04d.png" % k))
            k += 1
        b.close()
    rate = FPS / keep_every
    pal = os.path.join(frames_dir, "palette.png")
    scale = "scale=%d:-1:flags=lanczos" % a.width
    src = ["-framerate", "%g" % rate, "-i", os.path.join(frames_dir, "f_%04d.png")]
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error"] + src + ["-vf", scale + ",palettegen=max_colors=96:stats_mode=diff", pal])
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error"] + src + ["-i", pal, "-lavfi",
                          scale + " [x]; [x][1:v] paletteuse=dither=none:diff_mode=rectangle", "-loop", "0", a.out])
    mb = os.path.getsize(a.out) / 1e6
    print("wrote %s, %d frames, %.1f MB" % (os.path.relpath(a.out, ROOT), k, mb))
    if mb > 8:
        print("over 8 MB, try --fps 8 or --width 960")


if __name__ == "__main__":
    main()
