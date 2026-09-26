"""stage 1 panels and the shared header, account and log."""
import math

from ..brain import FEATS, N_KC, REAL_BEE_KC, REAL_BEE_NEURONS, clamp
from ..engine import POOLS_PER_DAY
from .canvas import (BOLD, BONE, DIM, GREEN, GREY, GREY_L, PINK, PINK_D, PINK_H, PINK_X, RED,
                     Canvas, big, big_width, money, spark, tone)

SUBTITLE = {
    1: "i put a simulated bee brain inside a trading pipeline. it scores pools. i click.",
    2: "the bee stopped sending one number. grok reads the whole waggle vector and decides when to wait.",
    3: "a ninth glomerulus: telegram velocity. the bee was never told what it means. it learned.",
}


def panel_brain(cv, s, x, y, w, h):
    cv.box(x, y, w, h, "BEE BRAIN", "five lobes, one pool at a time")
    ox, oy = x + w // 2, y + 2 + 13
    s.art.draw(cv, ox, oy)
    lab = [("optic lobe", -33, -10), ("optic lobe", 23, -10),
           ("mushroom bodies", -7, -12), ("central complex", -7, 3),
           ("antennal lobes", -22, 10), ("motor · seg", 9, 12)]
    stage_map = {"optic lobe": "optic", "mushroom bodies": "mushroom", "central complex": "central",
                 "antennal lobes": "antennal", "motor · seg": "motor"}
    for name, dx, dy in lab:
        on = s.stage == stage_map[name]
        cv.text(ox + dx, oy + dy, name, BOLD + PINK if on else GREY)
    yy = y + h - 3
    cv.text(x + 2, yy, "real bee %s neurons  drawn %d  kenyon %d of ~%s  spikes %d" % (
        "{:,}".format(REAL_BEE_NEURONS), s.art.total_cells(), N_KC, "{:,}".format(REAL_BEE_KC),
        s.art.fires), GREY)
    cv.text(x + 2, yy + 1, "each lit mushroom cell is an active kenyon cell in this pool's sparse code", DIM)


def panel_waggle(cv, s, x, y, w, h):
    e = s.e
    th = e.thought
    cv.box(x, y, w, h, "WAGGLE DANCE", "the output is a vector, not a number")
    # dance floor on the left
    fw = 26
    fh = min(h - 5, 15)
    fx = x + 3
    fy = y + 2 + max(0, (h - 5 - fh) // 2)
    cx, cy = fx + fw // 2, fy + fh // 2

    def to_xy(px, py):
        return cx + round(px * (fw / 2 - 1)), cy + round(py * (fh / 2 - 0.5))

    # the full figure eight for the current pool, always visible behind the bee
    t0 = s.waggle_t - (s.waggle_t % (4 * math.pi))
    for k in range(260):
        tx, ty = to_xy(*s.waggle_xy(t0 + k / 260 * 4 * math.pi))
        cv.put(tx, ty, "∙", PINK_D)
    # the bee and its fading trail
    n = len(s.trail)
    for i, (px, py) in enumerate(s.trail):
        tx, ty = to_xy(px, py)
        age = n - i
        if age <= 1:
            continue
        if age < 8:
            ch, col = "●", PINK_H
        elif age < 20:
            ch, col = "●", PINK
        elif age < 45:
            ch, col = "•", PINK
        else:
            ch, col = "•", PINK_D
        cv.put(tx, ty, ch, col)
    if s.trail:
        tx, ty = to_xy(*s.trail[-1])
        cv.put(tx, ty, "◉", BOLD + BONE)
    cv.text(fx - 1, fy + fh + 1, "run = score  wiggle = dissent", GREY)
    if not th:
        return
    bx = x + fw + 6
    bw = 13
    rows = [("mushroom", th["lobes"]["mushroom"],
             "seen %d, printed %d" % (th["seen"], th["won"])),
            ("antennal", th["lobes"]["antennal"],
             "noisy input" if th["lobes"]["antennal"] < 0.45 else "clean input"),
            ("optic", th["lobes"]["optic"],
             "narrative accelerating" if e.pool.obs["accel"] > 0.55 else "narrative flat"),
            ("central", th["lobes"]["central"],
             "explore" if th["explore"] else "exploit")]
    for i, (name, v, note) in enumerate(rows):
        ry = y + 2 + i * 2
        cv.text(bx, ry, name, GREY_L)
        cv.hbar(bx + 10, ry, bw, v, PINK if v >= .5 else PINK_D, "▇", "·")
        cv.text(bx + 11 + bw, ry, "%.2f" % v, BONE)
        cv.text(bx + 17 + bw, ry, note[:w - (bx - x) - bw - 19], GREY)
    ry = y + 2 + 4 * 2
    v = th["verdict"]
    col = GREEN if v == "PASS" else (RED if v == "SKIP" else BONE)
    cv.text(bx, ry, "motor", GREY_L)
    cv.text(bx + 10, ry, v, BOLD + col)
    if th["flag"]:
        cv.text(bx + 16, ry, "with a flag: antennal below 0.50", BONE)
    elif th["explore"]:
        cv.text(bx + 16, ry, "explore entry, small size", BONE)
    cv.text(bx, ry + 2, "consensus", GREY_L)
    cv.hbar(bx + 10, ry + 2, bw, th["consensus"], PINK_D, "▇", "·")
    cv.text(bx + 11 + bw, ry + 2, "%.2f" % th["consensus"], BONE)
    cv.text(bx + 17 + bw, ry + 2, "lobes agree" if th["consensus"] > .6 else "lobes argue", GREY)


def panel_pool(cv, s, x, y, w, h):
    e = s.e
    cv.box(x, y, w, h, "LIVE POOL", "what the antennae smell")
    p = e.pool
    if not p:
        return
    cv.text(x + 2, y + 2, p.name, BOLD + BONE)
    cv.text(x + 14, y + 2, p.addr, GREY)
    cv.rtext(x + w - 3, y + 2, "pool #%d" % p.id, GREY)
    bw = w - 30
    for i, f in enumerate(FEATS):
        ry = y + 4 + i
        v = p.obs[f]
        cv.text(x + 2, ry, f, GREY_L)
        if f == "bundle":
            cv.text(x + 15, ry, "yes" if v > .5 else "no", RED if v > .5 else GREY_L)
        else:
            cv.hbar(x + 15, ry, bw, v, PINK_D, "▇", "·")
            cv.text(x + 16 + bw, ry, "%.2f" % v, BONE)
    ry = y + 13
    cv.text(x + 2, ry, "input noise", GREY_L)
    cv.hbar(x + 15, ry, bw, p.noise, PINK_X, "▒", "·")
    cv.text(x + 16 + bw, ry, "%.2f" % p.noise, BONE)
    order = ["antennal", "optic", "mushroom", "central", "motor"]
    xx = x + 2
    for st in order:
        on = st == s.stage
        done = order.index(st) < order.index(s.stage) if s.stage in order else False
        cv.text(xx, y + h - 2, st, BOLD + PINK if on else (PINK_D if done else DIM))
        xx += len(st) + 2


def panel_memory(cv, s, x, y, w, h):
    e = s.e
    b = e.brain
    cv.box(x, y, w, h, "MUSHROOM MEMORY", "octopamine, punishment")
    ws = b.w
    hi = sum(1 for v in ws if v > 0.6)
    lo = sum(1 for v in ws if v < 0.4)
    cv.text(x + 2, y + 2, "kenyon cells trained toward print", GREY_L)
    cv.rtext(x + w - 3, y + 2, "%d" % hi, BONE)
    cv.text(x + 2, y + 3, "kenyon cells trained toward rug", GREY_L)
    cv.rtext(x + w - 3, y + 3, "%d" % lo, BONE)
    cv.text(x + 2, y + 4, "patterns in memory", GREY_L)
    cv.rtext(x + w - 3, y + 4, "%d" % len(b.memory), BONE)
    cv.text(x + 2, y + 5, "sugar / punishment broadcasts", GREY_L)
    cv.rtext(x + w - 3, y + 5, "%d / %d" % (b.sugar, b.pain), BONE)
    # weight histogram
    bins = [0] * (w - 6)
    for v in ws:
        bins[min(len(bins) - 1, int(v * len(bins)))] += 1
    m = max(bins) or 1
    ticks = " ▁▂▃▄▅▆▇█"
    cv.text(x + 3, y + 6, "".join(ticks[int(c / m * 8)] for c in bins), PINK_D)
    cv.text(x + 3, y + 7, "rug", GREY)
    cv.rtext(x + w - 3, y + 7, "print", GREY)
    ey = y + 9
    cv.text(x + 2, ey, "explore", GREY_L)
    cv.hbar(x + 11, ey, w - 20, b.eps / 0.5, PINK_D, "▇", "·")
    cv.rtext(x + w - 3, ey, "%.0f%%" % (b.eps * 100), BONE)
    cv.text(x + 2, ey + 1, "explores less as memory fills", DIM)


def panel_account(cv, s, x, y, w, h):
    e = s.e
    if s.live:
        return panel_live_account(cv, s, x, y, w, h)
    cv.box(x, y, w, h, "ACCOUNT", "sim, fees in")
    eq = e.equity
    txt = "{:,.0f}".format(eq)
    dbl = big_width(txt) <= w - 4
    col = GREEN if eq >= e.start else RED
    big(cv, x + 2, y + 2, txt, col, dbl)
    cv.text(x + 2, y + 8, "usd, from %s" % money(e.start), GREY)
    cv.rtext(x + w - 3, y + 8, "%+.0f%%" % ((eq / e.start - 1) * 100), col)
    hist = list(e.equity_hist)[-(w - 4):]
    cv.text(x + 2, y + 9, spark(hist), GREEN if eq >= e.start else RED)
    n = len(e.closed)
    wins = sum(1 for c in e.closed if c[1] > 0)
    rows = [("day", "%d" % (e.n // POOLS_PER_DAY + 1)),
            ("pools scored", "%d" % e.n),
            ("trades closed", "%d" % n),
            ("wins", "%d  %s" % (wins, ("%.0f%%" % (100 * wins / n)) if n else "")),
            ("max drawdown", "%.0f%%" % (e.max_dd * 100)),
            ("held through -30% and won", "%d" % e.hold_saves)]
    for i, (a, b) in enumerate(rows):
        cv.text(x + 2, y + 11 + i, a, GREY_L)
        cv.rtext(x + w - 3, y + 11 + i, b, BONE)
    vy = y + 11 + len(rows) + 1
    c = e.counts
    max(1, sum(c.values()))
    cv.text(x + 2, vy, "PASS %d" % c["PASS"], GREEN)
    cv.text(x + 14, vy, "WATCH %d" % c["WATCH"], BONE)
    cv.text(x + 27, vy, "SKIP %d" % c["SKIP"], RED)


def panel_live_account(cv, s, x, y, w, h):
    L = s.live
    L.advance(s.e.n)
    cv.box(x, y, w, h, "LIVE ACCOUNT", "your trades")
    eq = L.equity
    txt = "{:,.0f}".format(eq)
    col = GREEN if eq >= L.start else RED
    big(cv, x + 2, y + 2, txt, col, big_width(txt) <= w - 4)
    cv.text(x + 2, y + 8, "usd, from %s" % money(L.start), GREY)
    cv.rtext(x + w - 3, y + 8, "%+.0f%%" % ((eq / L.start - 1) * 100), col)
    cv.text(x + 2, y + 9, spark(L.hist[-(w - 4):]), col)
    done = L.done
    wins = sum(1 for t in done if t[3] > 0)
    best = max((t[3] for t in done), default=0)
    rows = [("day", "%d" % (s.e.n // POOLS_PER_DAY + 1)),
            ("trades closed", "%d of %d" % (len(done), len(L.trades))),
            ("wins", "%d  %s" % (wins, ("%.0f%%" % (100 * wins / len(done))) if done else "")),
            ("best trade", "%+.0f%%" % best if done else "-"),
            ("max drawdown", "%.0f%%" % (L.max_dd * 100))]
    for i, (a, b) in enumerate(rows):
        cv.text(x + 2, y + 11 + i, a, GREY_L)
        cv.rtext(x + w - 3, y + 11 + i, b, BONE)
    cv.text(x + 2, y + 18, "brain animation runs on sample pools", DIM)


def panel_open(cv, s, x, y, w, h):
    e = s.e
    if s.live:
        cv.box(x, y, w, h, "LAST TRADES", "yours")
        for i, t in enumerate(list(reversed(s.live.done))[:h - 3]):
            cv.text(x + 2, y + 2 + i, t[1][:10], BONE)
            cv.text(x + 14, y + 2 + i, money(t[2]), GREY)
            cv.rtext(x + w - 3, y + 2 + i, "%+.0f%%" % t[3], GREEN if t[3] > 0 else RED)
        if not s.live.done:
            cv.text(x + 2, y + 2, "first trade lands on its day", GREY)
        return
    cv.box(x, y, w, h, "OPEN", "max 4, the bee holds, i click")
    if not e.open:
        cv.text(x + 2, y + 2, "flat. waiting for a pass.", GREY)
    for i, p in enumerate(e.open[:h - 3]):
        ry = y + 2 + i
        r = p.ret
        cv.text(x + 2, ry, p.pool.name, BONE)
        cv.text(x + 13, ry, money(p.size), GREY)
        path = p.path[:p.age + 1][-12:]
        cv.text(x + 20, ry, spark(path, -0.9, 1.9), GREEN if r >= 0 else RED)
        cv.rtext(x + w - 3, ry, "%+.0f%%" % (r * 100), GREEN if r >= 0 else RED)


def panel_log(cv, s, x, y, w, h):
    cv.box(x, y, w, h, "HIVE LOG")
    rows = list(s.e.log)[-(h - 3):]
    for i, (t, msg, tn) in enumerate(rows):
        cv.text(x + 2, y + 2 + i, t, GREY)
        cv.text(x + 12, y + 2 + i, msg[:w - 14], tone(tn))


def header(cv, s, w):
    cv.text(1, 0, "NERVE", BOLD + PINK)
    cv.text(7, 0, "BEEBRAIN", BOLD + PINK_H)
    x = 17
    for i, name in enumerate(("brain", "grok", "telegram", "jev", "router", "arena")):
        lab = "%d %s" % (i + 1, name)
        cv.text(x, 0, lab, BOLD + PINK if i == s.post - 1 else DIM)
        x += len(lab) + 3
    cv.rtext(w - 1, 0, "%s  %s" % (s.e.stamp(), "your trades, sample pools" if s.live
             else "synthetic pools, sim account"), GREY)
    cv.text(1, 1, SUBTITLE.get(s.post, ""), GREY)


def build_wide(s, W, H):
    cv = Canvas(W, H)
    header(cv, s, W)
    top = 3
    lw = 82
    rw = W - lw - 3
    mw = (rw - 1) // 2
    panel_brain(cv, s, 1, top, lw, 31)
    panel_waggle(cv, s, 1, top + 31, lw, H - top - 32)
    x2 = lw + 2
    x3 = x2 + mw + 1
    w3 = W - x3 - 1
    panel_pool(cv, s, x2, top, mw, 17)
    panel_memory(cv, s, x2, top + 17, mw, 12)
    panel_log(cv, s, x2, top + 29, mw, H - top - 30)
    panel_account(cv, s, x3, top, w3, 21)
    panel_open(cv, s, x3, top + 21, w3, 7)
    cv.box(x3, top + 28, w3, H - top - 29, "LOBES", "live cell activity")
    notes = [("antennal", "8 glomeruli, one per feature"),
             ("optic", "60 ticks of narrative heat"),
             ("mushroom", "2,000 kenyon cells, 5% fire"),
             ("central", "ring bump, explore or exploit"),
             ("motor", "PASS, WATCH or SKIP")]
    for i, (a, b) in enumerate(notes):
        ry = top + 30 + i * 3
        if ry + 1 >= H - 2:
            break
        on = s.stage == a
        cells = s.art.cells[a]
        lvl = max(0.0, sum(c[2] for c in cells) / max(1, len(cells)) - 0.14) * 1.4
        cv.text(x3 + 2, ry, a, BOLD + PINK if on else PINK_D)
        cv.hbar(x3 + 12, ry, w3 - 22, clamp(lvl * 2.5), PINK if on else PINK_X, "▇", "·")
        cv.rtext(x3 + w3 - 3, ry, "%3.0f%%" % (clamp(lvl * 2.5) * 100), BONE if on else GREY)
        cv.text(x3 + 12, ry + 1, b[:w3 - 14], GREY_L if on else GREY)
    cv.text(1, H - 1, "the bee does not say yes or no. it shows which part of the brain agrees.", GREY)
    return cv


def build_compact(s, W, H):
    cv = Canvas(W, H)
    header(cv, s, W)
    top = 3
    panel_brain(cv, s, 1, top, 82, 31)
    panel_waggle(cv, s, 1, top + 31, 82, 14)
    panel_account(cv, s, 1, top + 45, 82, 21)
    panel_log(cv, s, 1, top + 66, 82, max(5, H - top - 67))
    return cv
