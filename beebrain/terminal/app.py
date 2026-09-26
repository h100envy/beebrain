"""the terminal loop. picks a stage and a layout, then draws one frame per tick."""
import shutil
import sys
import time

from ..engine import START_CASH, GROK_START, TG_START
from ..live import Live
from .canvas import BG, ESC, GREY, PINK
from .grok import build_compact2, build_wide2
from .panels import build_compact, build_wide
from .shows import Show, Show2, Show3b
from .telegram import build_compact3b, build_wide3b

FPS = 12
STAGES = {1: (build_wide, build_compact), 2: (build_wide2, build_compact2), 3: (build_wide3b, build_compact3b)}
WIDE_MIN = (176, 50)
COMPACT_W = 84


def geometry(post, layout, width=0, height=0, term=None):
    """returns (layout, W, H, need). term is (columns, lines)."""
    cols, lines = term or tuple(shutil.get_terminal_size((180, 52)))
    if layout == "auto":
        layout = "wide" if (cols >= WIDE_MIN[0] and lines >= WIDE_MIN[1]) else "compact"
    if layout == "wide":
        W = width or max(WIDE_MIN[0], min(cols, 210))
        H = height or max(WIDE_MIN[1], min(lines, 64))
        need = WIDE_MIN
    else:
        ch = {2: 82, 3: 82}.get(post, 76)
        W = width or COMPACT_W
        H = height or max(ch, min(lines, ch + 4))
        need = (COMPACT_W, ch)
    return layout, W, H, need


def make_show(post, seed, speed, start=START_CASH, trades=""):
    if post == 2:
        s = Show2(seed, speed, start if start != START_CASH else GROK_START)
    elif post == 3:
        s = Show3b(seed, speed, start if start != START_CASH else TG_START)
    else:
        s = Show(seed, speed)
    if trades:
        s.live = Live(trades, start)
        s.live.log = s.e.log
    return s


def frame(post, layout, s, W, H):
    wide, compact = STAGES[post]
    return (wide if layout == "wide" else compact)(s, W, H)


def run(post=1, layout="auto", speed=1.0, seed=5, trades="", start=START_CASH,
        frames=0, plain=False, width=0, height=0, out=None):
    out = out or sys.stdout
    ts = tuple(shutil.get_terminal_size((180, 52)))
    layout, W, H, need = geometry(post, layout, width, height, ts)
    if not (width or plain) and (ts[0] < need[0] or ts[1] < need[1] - 6):
        R = ESC + "0m"
        out.write("%sNERVE BEEBRAIN needs a bigger window.%s\n" % (PINK, R))
        out.write("%shave %dx%d, the %s layout wants %dx%d.%s\n" % (GREY, ts[0], ts[1], layout, need[0], need[1], R))
        out.write("%smake the font smaller with cmd minus, or force it with --width and --height.%s\n" % (GREY, R))
        return 2
    s = make_show(post, seed, speed, start, trades)
    if not plain:
        out.write("\x1b[?1049h\x1b[?25l" + BG + "\x1b[2J")
    try:
        while True:
            s.step()
            if not plain:
                out.write("\x1b[H" + frame(post, layout, s, W, H).render())
                out.flush()
                time.sleep(1 / FPS)
            if frames and s.frame >= frames:
                break
    except KeyboardInterrupt:
        pass
    finally:
        if not plain:
            out.write(ESC + "0m\x1b[?25h\x1b[?1049l")
            out.flush()
    if plain:
        out.write(frame(post, layout, s, W, H).render() + "\n")
    return 0
