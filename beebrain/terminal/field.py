"""
beebrain trade: the bee on real pools, in the terminal.

a feed thread polls the public apis. the main loop scores one pool at a time and
walks it through the drawn brain, the same way the sim terminal does. three paper
accounts race: you, the bee on autopilot, and a random baseline.

keys: b buy the last pool the bee passed with $50 of your paper cash
      s sell your oldest open position
      q quit. the session is saved and picks up where it left off.
"""
import json
import math
import os
import queue
import random
import select
import sys
import threading
import time

from ..brain import FEATS, N_KC
from ..field.feed import Feed, now_ms
from ..field.features import LIVE_LABELS
from ..field.session import FieldSession
from .art import BrainArt
from .canvas import (AMBER, BG, BOLD, BONE, DIM, ESC, GREEN, GREY, GREY_L, PINK, PINK_D, PINK_H, RED, Canvas,
                     big, big_width, tone)

FPS = 12
SCORE_EVERY_S = 1.6
MARK_EVERY_S = 2.0
SAVE_EVERY_S = 30.0
BUY_USD = 50.0
STAGES = ("antennal", "optic", "mushroom", "central", "motor")


def state_path(chain):
    return os.path.join(os.path.expanduser("~"), ".beebrain", "field-%s.json" % chain)


def load_session(chain, fresh=False):
    p = state_path(chain)
    if not fresh and os.path.exists(p):
        try:
            with open(p) as fh:
                return FieldSession.from_json(json.load(fh))
        except (ValueError, KeyError, OSError):
            pass
    return FieldSession(chain)


def save_session(s):
    p = state_path(s.chain)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(s.to_json(), fh)
    os.replace(tmp, p)


class Poller(threading.Thread):
    """network off the draw loop. results go through a queue."""

    def __init__(self, feed, tracked_fn):
        super().__init__(daemon=True)
        self.feed, self.tracked_fn = feed, tracked_fn
        self.out = queue.Queue()
        self.stop = threading.Event()

    def run(self):
        while not self.stop.is_set():
            new, fresh = self.feed.poll(time.time(), self.tracked_fn())
            if new or fresh:
                self.out.put((new, fresh))
            self.stop.wait(2.0)


class FieldShow:
    def __init__(self, session, feed=None, clock=None):
        self.s = session
        self.feed = feed
        self.clock = clock or now_ms
        self.art = BrainArt(random.Random(7))
        self.frame = 0
        self.stage = "idle"
        self.stage_t = 0
        self.t_score = self.t_mark = self.t_save = 0.0
        self.note = ""

    def ingest(self, new, fresh):
        t = self.clock()
        self.s.ingest(new, t)
        self.s.ingest(fresh, t)

    def step(self):
        t = self.clock()
        sec = t / 1000.0
        if sec - self.t_mark >= MARK_EVERY_S:
            self.t_mark = sec
            self.s.mark(t)
        if sec - self.t_score >= SCORE_EVERY_S and self.s.queue:
            self.t_score = sec
            if self.s.score_next(t):
                self.stage, self.stage_t = "antennal", self.frame
                self.fire("antennal")
        # walk the last pool through the lobes, a few frames per stage
        if self.stage in STAGES:
            k = (self.frame - self.stage_t) // 3
            want = STAGES[min(k, 4)]
            if want != self.stage:
                self.stage = want
                self.fire(want)
        self.art.step()
        self.frame += 1

    def fire(self, stage):
        r, art = self.s.last, self.art
        if not r:
            return
        o = r["obs"]
        if stage == "antennal":
            n = len(art.cells["antennal"])
            art.excite("antennal", lambda i, c: o[FEATS[i * 8 // n]] * (1 - 0.6 * r["noise"]))
        elif stage == "optic":
            art.excite("optic", lambda i, c: (0.4 * o["heat"] + 0.6 * o["accel"]) * (0.6 + 0.4 * math.sin(c[1] * 0.7 + self.frame)))
        elif stage == "mushroom":
            act = set(r["act"])
            art.excite("mushroom", lambda i, c: 1.0 if (i * 37) % N_KC in act or ((i * 37 + 1) % N_KC) in act else 0.05)
        elif stage == "central":
            xs = [c[0] for c in art.cells["central"]]
            lo, hi = min(xs), max(xs)
            pos = lo + (hi - lo) * max(0.0, min(1.0, (r["comb"] - 0.3) / 0.5))
            art.excite("central", lambda i, c: math.exp(-((c[0] - pos) ** 2) / 6.0))
        elif stage == "motor":
            v = r["verdict"]
            art.seg_col = GREEN if v == "PASS" else (RED if v == "SKIP" else BONE)
            art.excite("motor", lambda i, c: 1.0)
        art.fire(stage)

    def buy_last_pass(self):
        for r in reversed(self.s.recent):
            if r["verdict"] == "PASS":
                pos = self.s.buy(r["pair"], BUY_USD, self.clock())
                self.note = "bought $%s" % r["symbol"] if pos else "no cash for that"
                return
        self.note = "no PASS yet"

    def sell_oldest(self):
        you = self.s.accounts["you"]
        if you.open:
            self.s.sell(you.open[0].id, self.clock())
        else:
            self.note = "nothing open"


# ----------------------------------------------------------------- panels ---
def age_txt(ms_now, created):
    if not created:
        return "?"
    m = (ms_now - created) / 60000.0
    return "%dm" % m if m < 90 else ("%.0fh" % (m / 60) if m < 2880 else "%.0fd" % (m / 1440))


def usd(v):
    if v >= 1e6:
        return "$%.1fm" % (v / 1e6)
    if v >= 1e3:
        return "$%.0fk" % (v / 1e3)
    return "$%.0f" % v


def vcol(v):
    return GREEN if v == "PASS" else (RED if v == "SKIP" else AMBER)


def header(cv, fs, W):
    s = fs.s
    cv.text(1, 0, "NERVE", BOLD + PINK)
    cv.text(7, 0, "BEEBRAIN", BOLD + PINK_H)
    cv.text(17, 0, "FIELD", BOLD + AMBER)
    cv.text(24, 0, "live pools on %s" % s.chain, BONE)
    st = fs.feed.status if fs.feed else "offline"
    cv.rtext(W - 1, 0, "%s · paper accounts · read only data · not advice" % st, GREY)
    cv.text(1, 1, "real pools, real prices, paper money. the bee scores, you race it. b buy last pass  s sell  q quit", GREY)


def panel_brain(cv, fs, x, y, w, h):
    s = fs.s
    cv.box(x, y, w, h, "BEE BRAIN", "the same brain, real senses")
    fs.art.draw(cv, x + w // 2, y + 15)
    r = s.last
    if r:
        cv.text(x + 2, y + h - 3, "%s  %s  liq %s  %s" % (r["symbol"], r["verdict"], usd(r["liq"]), fs.stage), BONE)
        cv.text(x + 2, y + h - 2, ("reflex: " + r["reasons"][0]) if r["reasons"] else "reached the lobes", GREY)


def panel_senses(cv, fs, x, y, w, h):
    s = fs.s
    cv.box(x, y, w, h, "WHAT THE ANTENNAE SMELL", "live features")
    r = s.last
    if not r:
        cv.text(x + 2, y + 2, "waiting for the first pool", GREY)
        return
    bw = w - 34
    for i, f in enumerate(FEATS):
        ry = y + 2 + i
        v = r["obs"][f]
        cv.text(x + 2, ry, LIVE_LABELS[f], GREY_L)
        if f == "bundle":
            cv.text(x + 18, ry, "tripped" if v > .5 else "clear", RED if v > .5 else GREY_L)
            continue
        cv.hbar(x + 18, ry, bw, v, PINK_D, "▇", "·")
        cv.text(x + 19 + bw, ry, "%.2f" % v, BONE)
    ry = y + 11
    cv.text(x + 2, ry, "noise", GREY_L)
    cv.hbar(x + 18, ry, bw, r["noise"], PINK_D, "▒", "·")
    cv.text(x + 19 + bw, ry, "%.2f" % r["noise"], BONE)
    vec = r["vector"]
    ry += 2
    for i, k in enumerate(("mushroom", "antennal", "optic", "central")):
        cv.text(x + 2 + i * 19, ry, "%s %.2f" % (k, vec[k]["value"]), PINK if vec[k]["value"] >= .5 else PINK_D)
    cv.text(x + 2, ry + 1, "motor", GREY_L)
    cv.text(x + 8, ry + 1, r["verdict"], BOLD + vcol(r["verdict"]))
    cv.text(x + 16, ry + 1, "consensus %.2f   %s" % (vec["consensus"], "explore" if r["explore"] else "exploit"), GREY)


def panel_field(cv, fs, x, y, w, h):
    s = fs.s
    cv.box(x, y, w, h, "THE FIELD", "%d scored · %d queued" % (s.scored, len(s.queue)))
    cv.text(x + 2, y + 1, "pool        age   liq     1h vol  verdict", GREY)
    t = fs.clock()
    rows = list(s.recent)[-(h - 3):][::-1]
    for i, r in enumerate(rows):
        ry = y + 2 + i
        sn = s.field.get(r["pair"], {})
        cv.text(x + 2, ry, ("$" + r["symbol"])[:11], BONE if r["verdict"] != "SKIP" else GREY_L)
        cv.text(x + 14, ry, age_txt(t, sn.get("created_ms", 0)), GREY)
        cv.text(x + 20, ry, usd(r["liq"]), GREY_L)
        cv.text(x + 28, ry, usd(sn.get("vol_h1", 0)), GREY_L)
        cv.text(x + 36, ry, r["verdict"].lower(), vcol(r["verdict"]))
        tag = r["reasons"][0] if r["reasons"] else ("bee in" if r.get("took") else "%.2f" % r["comb"])
        cv.text(x + 43, ry, tag[:w - 45], GREY if r["reasons"] else (AMBER if r.get("took") else DIM))


def panel_race(cv, fs, x, y, w, h):
    s = fs.s
    cv.box(x, y, w, h, "THE RACE", "paper, from $500")
    for i, name in enumerate(("bee", "random", "you")):
        a = s.accounts[name]
        st = a.stats()
        ry = y + 2 + i * 6
        eq = a.equity
        col = GREEN if eq >= a.start else RED
        cv.text(x + 2, ry, {"bee": "the bee", "random": "random baseline", "you": "you"}[name], BOLD + (PINK if name == "bee" else BONE))
        cv.rtext(x + w - 3, ry, "%+.1f%%" % ((eq / a.start - 1) * 100), col)
        txt = "{:,.0f}".format(eq)
        if big_width(txt, False) <= w - 4:
            big(cv, x + 2, ry + 1, txt, col, False)
        cv.text(x + 20, ry + 2, "%d trades, %d won" % (st["trades"], st["wins"]), GREY_L)
        cv.text(x + 20, ry + 3, "%d open, dd %.0f%%" % (st["open"], st["max_drawdown"] * 100), GREY)
    ry = y + 20
    cv.text(x + 2, ry, "open", GREY)
    k = 0
    for name in ("you", "bee"):
        for p in s.accounts[name].open:
            if ry + 1 + k >= y + h - 1:
                break
            r = p.ret()
            cv.text(x + 2, ry + 1 + k, name, PINK if name == "bee" else BONE)
            cv.text(x + 7, ry + 1 + k, ("$" + p.symbol)[:10], BONE)
            cv.text(x + 19, ry + 1 + k, "$%.0f" % p.size, GREY)
            cv.rtext(x + w - 3, ry + 1 + k, "%+.0f%%" % (r * 100), GREEN if r >= 0 else RED)
            k += 1
    if k == 0:
        cv.text(x + 2, ry + 1, "flat", GREY)


def panel_forward(cv, fs, x, y, w, h):
    s = fs.s
    cv.box(x, y, w, h, "FORWARD TEST", "+%d min, fees in" % s.horizon_min)
    fw = s.forward()
    cv.text(x + 2, y + 2, "verdict   pools   hit     avg net", GREY)
    for i, v in enumerate(("PASS", "WATCH", "SKIP")):
        f = fw[v]
        ry = y + 3 + i
        cv.text(x + 2, ry, v, vcol(v))
        cv.text(x + 12, ry, "%d" % f["n"], BONE)
        cv.text(x + 20, ry, ("%.0f%%" % (f["hit"] * 100)) if f["n"] else "-", BONE)
        cv.text(x + 28, ry, ("%+.1f%%" % (f["avg_net"] * 100)) if f["n"] else "-", GREEN if f["avg_net"] > 0 else RED)
    cv.text(x + 2, y + 7, "pending %d  dropped %d" % (len(s.shadows), s.fwd_dropped), GREY)
    g = s.gate()
    cv.text(x + 2, y + 9, "GRADUATION", BOLD + (GREEN if g["open"] else AMBER))
    cv.text(x + 14, y + 9, "open, earned a real look" if g["open"] else "closed, paper only", GREY_L)
    for i, (name, ok, val) in enumerate(g["checks"]):
        cv.text(x + 2, y + 10 + i, ("✓ " if ok else "· ") + name, GREEN if ok else GREY_L)
        cv.rtext(x + w - 2, y + 10 + i, val, BONE)
    b = s.brain
    cv.text(x + 2, y + 14, "sugar %d  punishment %d" % (b.sugar, b.pain), GREY)
    cv.text(x + 2, y + 15, "explore %.0f%%" % (b.eps * 100), GREY)


def panel_log(cv, fs, x, y, w, h):
    s = fs.s
    cv.box(x, y, w, h, "HIVE LOG")
    rows = list(s.log)[-(h - 3):]
    for i, (t, msg, tn) in enumerate(rows):
        cv.text(x + 2, y + 2 + i, time.strftime("%H:%M", time.localtime(t / 1000)), GREY)
        cv.text(x + 9, y + 2 + i, msg[:w - 11], tone(tn))
    if fs.note:
        cv.rtext(x + w - 3, y, " " + fs.note + " ", AMBER)


def build_wide(fs, W, H):
    cv = Canvas(W, H)
    header(cv, fs, W)
    top = 3
    panel_brain(cv, fs, 1, top, 82, 31)
    panel_senses(cv, fs, 1, top + 31, 82, H - top - 32)
    x2, w2 = 84, 50
    panel_field(cv, fs, x2, top, w2, 30)
    panel_log(cv, fs, x2, top + 30, w2, H - top - 31)
    x3 = x2 + w2 + 1
    w3 = W - x3 - 1
    panel_race(cv, fs, x3, top, w3, 30)
    panel_forward(cv, fs, x3, top + 30, w3, H - top - 31)
    cv.text(1, H - 1, "paper only. prices from dexscreener and geckoterminal. the bee is uncalibrated. not financial advice.", DIM)
    return cv


def build_compact(fs, W, H):
    cv = Canvas(W, H)
    header(cv, fs, W)
    top = 3
    panel_senses(cv, fs, 1, top, 82, 16)
    panel_field(cv, fs, 1, top + 16, 82, 20)
    panel_race(cv, fs, 1, top + 36, 82, 26)
    panel_forward(cv, fs, 1, top + 62, 82, 16)
    panel_log(cv, fs, 1, top + 78, 82, max(6, H - top - 79))
    return cv


# ------------------------------------------------------------------- loop ---
class Keys:
    def __init__(self):
        self.ok = sys.stdin.isatty()
        self.old = None

    def __enter__(self):
        if self.ok:
            import termios
            import tty
            self.old = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, *a):
        if self.old is not None:
            import termios
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old)

    def read(self):
        if self.ok and select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return ""


def run(chain="solana", layout="auto", fresh=False, frames=0, plain=False, width=0, height=0, out=None,
        fetch=None, clock=None, save=True):
    import shutil
    out = out or sys.stdout
    cols, lines = shutil.get_terminal_size((180, 52))
    if layout == "auto":
        layout = "wide" if cols >= 176 and lines >= 50 else "compact"
    W, H = (width or max(176, min(cols, 210)), height or max(50, min(lines, 64))) if layout == "wide" else (width or 84, height or 96)
    build = build_wide if layout == "wide" else build_compact
    s = load_session(chain, fresh) if save else FieldSession(chain)
    feed = Feed(chain, fetch=fetch) if fetch else Feed(chain)
    fs = FieldShow(s, feed, clock)
    if plain and clock is None:
        base = now_ms()
        fs.clock = lambda: base + fs.frame * 1000.0 / FPS      # frames stand in for time
    poller = None
    if plain:
        new, fresh_ = feed.poll(time.time(), [])
        fs.ingest(new, fresh_)
    else:
        poller = Poller(feed, s.tracked)
        poller.start()
        out.write("\x1b[?1049h\x1b[?25l" + BG + "\x1b[2J")
    try:
        with Keys() as keys:
            while True:
                if poller:
                    while not poller.out.empty():
                        fs.ingest(*poller.out.get())
                k = "" if plain else keys.read()
                if k == "q":
                    break
                if k == "b":
                    fs.buy_last_pass()
                if k == "s":
                    fs.sell_oldest()
                fs.step()
                if not plain:
                    out.write("\x1b[H" + build(fs, W, H).render())
                    out.flush()
                    time.sleep(1 / FPS)
                    if save and time.time() - fs.t_save > SAVE_EVERY_S:
                        fs.t_save = time.time()
                        save_session(s)
                if frames and fs.frame >= frames:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        if poller:
            poller.stop.set()
        if not plain:
            out.write(ESC + "0m\x1b[?25h\x1b[?1049l")
            out.flush()
        if save:
            save_session(s)
    if plain:
        out.write(build(fs, W, H).render() + "\n")
    return 0
