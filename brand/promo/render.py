"""
renders brand/promo/promo.html to an mp4 for x: 1080x1350, 30 fps, h264, no metadata.

  python brand/promo/render.py [out.mp4]        full video
  python brand/promo/render.py --stills 2,7,13,18,22,25   pngs of these seconds

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import base64
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FPS = 30


def main():
    from playwright.sync_api import sync_playwright
    args = sys.argv[1:]
    stills = None
    if args and args[0] == "--stills":
        stills = [float(x) for x in args[1].split(",")]
        args = args[2:]
    out = args[0] if args else os.path.join(ROOT, "build", "promo", "beebrain-promo.mp4")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        pg.goto("file://" + os.path.join(HERE, "promo.html"))
        pg.evaluate("document.fonts.ready")
        pg.evaluate("Promise.all([...document.fonts].map(f => f.load()))")
        pg.wait_for_timeout(300)

        def frame(t):
            pg.evaluate("t => window.draw(t)", t)
            return base64.b64decode(pg.evaluate("document.getElementById('cv').toDataURL('image/png')").split(",", 1)[1])

        if stills:
            for t in stills:
                path = os.path.join(os.path.dirname(out), "still_%04.1f.png" % t)
                open(path, "wb").write(frame(t))
                print("wrote", path)
            b.close()
            return
        dur = pg.evaluate("window.DUR")
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
                               "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-level", "4.1",
                               "-pix_fmt", "yuv420p", "-map_metadata", "-1", "-movflags", "+faststart", out], stdin=subprocess.PIPE)
        n = int(dur * FPS)
        for k in range(n):
            ff.stdin.write(frame(k / FPS))
            if k % 90 == 0:
                print("frame %d / %d" % (k, n), flush=True)
        ff.stdin.close()
        ff.wait()
        b.close()
    print("wrote", out)


if __name__ == "__main__":
    main()
