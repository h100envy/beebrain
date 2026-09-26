"""stage 2: the bee talks, a rule based reader standing in for grok listens."""
import math
import random

from ..engine import DIRTY
from .canvas import (AMBER, BOLD, BONE, DIM, ESC, GREEN, GREY, GREY_L, LINE, PINK, PINK_D, PINK_H,
                     PINK_X, RED, Canvas, big, big_width, money, tone)
from .panels import header, panel_account


def panel_packet(cv, s, x, y, w, h):
    e = s.e
    cv.box(x, y, w, h, "WAGGLE PACKET", "what the bee sends grok")
    g = e.grok
    if not g:
        cv.text(x + 2, y + 2, "waiting for the first pass", GREY)
        return
    cv.text(x + 2, y + 2, "{", GREY)
    cv.text(x + 4, y + 3, '"pool":', GREY)
    cv.text(x + 16, y + 3, '"%s",' % g["name"], BONE)
    bw = 16
    for i, (name, v, note) in enumerate(g["packet"]):
        ry = y + 4 + i
        bad = name == "antennal" and v < DIRTY
        cv.text(x + 4, ry, '"%s":' % name, GREY)
        cv.text(x + 16, ry, "%.2f," % v, RED if bad else BONE)
        cv.hbar(x + 23, ry, bw, v, RED if bad else (PINK if v >= .5 else PINK_D), "▇", "·")
        cv.text(x + 25 + bw, ry, note[:w - 28 - bw], RED if bad else GREY)
    ry = y + 4 + len(g["packet"])
    cv.text(x + 4, ry, '"motor":', GREY)
    cv.text(x + 16, ry, '"%s"' % g["verdict"], GREEN if g["verdict"] == "PASS" else BONE)
    if g["flag"]:
        cv.text(x + 25, ry, "flag: antennal below %.2f" % DIRTY, AMBER)
    cv.text(x + 2, ry + 1, "}", GREY)
    # the wire to grok, a pulse runs along it
    wy = ry + 2
    wire = "─" * (w - 16)
    cv.text(x + 2, wy, wire, PINK_X)
    pos = (s.frame * 2) % len(wire)
    cv.text(x + 2 + pos, wy, "◆", PINK_H)
    cv.text(x + w - 13, wy, "▶ grok", BOLD + PINK)
    cv.text(x + 2, wy + 1, "old output", GREY)
    cv.text(x + 14, wy + 1, "confidence %.2f" % g["old"], DIM)
    cv.text(x + 36, wy + 1, "new output", GREY)
    cv.text(x + 48, wy + 1, "which lobe voted for what", PINK_H)
    hy = wy + 3
    if hy + 1 < y + h - 1 and e.packets:
        cv.text(x + 2, hy, "recent packets        one number   antennal   grok", GREY)
        for i, (n, c, a, d) in enumerate(list(e.packets)[::-1][:y + h - hy - 2]):
            ry = hy + 1 + i
            cv.text(x + 2, ry, n[:12], BONE)
            cv.text(x + 24, ry, "%.2f" % c, DIM)
            cv.text(x + 37, ry, "%.2f" % a, RED if a < DIRTY else GREY_L)
            cv.text(x + 48, ry, d.lower(), AMBER if d == "WAIT" else GREEN)


def panel_grok(cv, s, x, y, w, h):
    e = s.e
    cv.box(x, y, w, h, "GROK", "reads the vector, simulated reader")
    g = e.grok
    if not g:
        cv.text(x + 2, y + 2, "no packet yet", GREY)
        return
    cv.text(x + 2, y + 2, g["name"], BOLD + BONE)
    shown = max(1, (s.frame - s.gt0) // 2 + 1)
    for i, (txt, tn) in enumerate(g["lines"][:shown]):
        ry = y + 4 + i
        if ry >= y + h - 5:
            break
        cv.text(x + 2, ry, ("> " + txt)[:w - 4], tone(tn))
    if shown > len(g["lines"]) and g["decision"]:
        d, why = g["decision"]
        col = GREEN if d == "ENTER" else (RED if d == "SKIP" else AMBER)
        cv.text(x + 2, y + h - 4, "decision", GREY)
        cv.text(x + 12, y + h - 4, d, BOLD + col)
        cv.text(x + 12 + len(d) + 2, y + h - 4, why[:w - 18 - len(d)], GREY_L)
        if d == "WAIT":
            left = s.cycle - (s.f % s.cycle)
            cv.text(x + 2, y + h - 3, "re-read in %d frames" % left, AMBER)


def panel_ledger(cv, s, x, y, w, h):
    e = s.e
    cv.box(x, y, w, h, "OVERRIDE LEDGER", "every time grok waited")
    cv.text(x + 2, y + 2, "time      pool       grok   if now", GREY)
    cv.rtext(x + w - 3, y + 2, "wait", GREY)
    rows = list(e.ledger)[-(h - 5):]
    for i, (t, name, d, fin, now, gp, saved, rug) in enumerate(reversed(rows)):
        ry = y + 3 + i
        cv.text(x + 2, ry, t, GREY)
        cv.text(x + 12, ry, name[:10], BONE)
        cv.text(x + 23, ry, d.lower(), GREEN if d == "ENTER" else RED)
        cv.text(x + 30, ry, ("%+.0f%%%s" % (fin * 100, " rug" if rug else ""))[:11], RED if fin < 0 else GREEN)
        cv.rtext(x + w - 3, ry, "%s%s" % ("+" if saved >= 0 else "-", money(abs(saved))), GREEN if saved >= 0 else RED)
    if not rows:
        cv.text(x + 2, y + 4, "no waits yet. grok waits only when memory", GREY)
        cv.text(x + 2, y + 5, "and shape say yes but the data is dirty.", GREY)


def panel_stats(cv, s, x, y, w, h):
    e = s.e
    st = e.st
    cv.box(x, y, w, h, "WHEN GROK LISTENS", "counterfactual")
    v = st["saved"]
    txt = "{:,.0f}".format(abs(v))
    col = GREEN if v >= 0 else RED
    cv.text(x + 2, y + 2, "net saved by waiting", GREY)
    cv.text(x + 2, y + 4, "+" if v >= 0 else "-", BOLD + col)
    big(cv, x + 4, y + 3, txt, col, big_width(txt) <= w - 8)
    rows = [("bee memory carried from stage 1", "%d pools" % e.warm_pools), ("pools scored here", "%d" % e.n), ("packets sent to grok", "%d" % st["sent"]),
            ("entered at once", "%d" % st["now"]), ("grok waited", "%d" % st["waits"]),
            ("skipped after re-read, would have lost", "%d" % st["avoided"]), ("skipped after re-read, would have won", "%d" % st["missed"]),
            ("entered after the wait, a bit later", "%d" % st["late"]),
            ("rugs dodged", "%d" % st["rugs_dodged"])]
    for i, (a, b) in enumerate(rows):
        ry = y + 10 + i
        if ry >= y + h - 2:
            break
        cv.text(x + 2, ry, a, GREY_L)
        cv.rtext(x + w - 3, ry, b, BONE)


def _ell(cx, cy, rx, ry, n=90):
    pts = set()
    for k in range(n):
        t = k / n * 2 * math.pi
        pts.add((round(cx + rx * math.cos(t)), round(cy + ry * math.sin(t))))
    return pts


def _arc(p0, p1, p2, k=40):
    out = []
    for i in range(k + 1):
        u = i / k
        x = (1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0]
        y = (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]
        pt = (round(x), round(y))
        if not out or out[-1] != pt:
            out.append(pt)
    return out


def panel_heads(cv, s, x, y, w, h):
    """stage 2 hero: the bee's head on the left, grok's head on the right, the waggle packet between."""
    e = s.e
    g = e.grok
    cv.box(x, y, w, h, "TWO HEADS", "the bee talks, grok listens")
    t = s.frame - s.gt0 if g else 999
    vals = {n: v for n, v, _ in g["packet"]} if g else {}
    rng = random.Random(s.frame // 3)
    # ------------------------------------------------------------ bee head
    bx, by = x + 18, y + 15
    for (px, py) in _ell(bx, by, 15, 9, 160):
        cv.put(px, py, "·", PINK_D)
    for sx in (-1, 1):                                   # compound eyes, amber facets
        ex = bx + sx * 11
        for dy in range(-6, 7):
            for dx in range(-3, 4):
                if (dx / 3.5) ** 2 + (dy / 6.5) ** 2 <= 1:
                    lit = rng.random() < 0.22
                    cv.put(ex + dx, by + dy, "●" if lit else "•", AMBER if lit else ESC + "38;5;130m")
        cv.put(ex - sx, by - 4, "◉", BONE)
        for (px, py) in _arc((bx + sx * 3, by - 9), (bx + sx * 4, by - 13), (bx + sx * 10, by - 13), 12):
            cv.put(px, py, "·", GREY_L)                  # antennae
        cv.put(bx + sx * 10, by - 13, "●", AMBER)
    for dx in (-2, 0, 2):                                # ocelli
        cv.put(bx + dx, by - 7 + (0 if dx == 0 else 1), "∘", BONE)

    def lvl(name):
        v = vals.get(name, 0.3)
        return BOLD + PINK_H if v >= 0.7 else (PINK if v >= 0.5 else (PINK_D if v >= 0.35 else PINK_X))
    for dx in (-4, -2, 2, 4):
        cv.put(bx + dx, by - 4, "◡", lvl("mushroom"))
    cv.text(bx - 3, by - 2, "═══════", lvl("central"))
    cv.text(bx - 7, by - 1, "))", lvl("optic"))
    cv.text(bx + 6, by - 1, "((", lvl("optic"))
    ant = vals.get("antennal", 0.6)
    acol = RED if ant < DIRTY else lvl("antennal")
    cv.text(bx - 4, by + 1, "(●)", acol)
    cv.text(bx + 2, by + 1, "(●)", acol)
    cv.text(bx - 2, by + 4, "▁▁▁▁▁", lvl("central"))
    cv.text(bx - 2, by + 7, "╰─┬─╯", GREY)
    cv.text(bx - 3, by + 11, "the bee", BOLD + PINK)
    if g and g["flag"]:
        cv.text(bx - 11, by + 12, "antennal %.2f, data dirty" % ant, RED)
    # ------------------------------------------------------------ grok head
    gx, gy = x + w - 18, y + 15
    ring = sorted(_ell(gx, gy, 15, 9, 220), key=lambda p: math.atan2((p[1] - gy) / 9, (p[0] - gx) / 15))
    rot = s.frame % len(ring)
    for i, (px, py) in enumerate(ring):
        k = (i - rot) % len(ring)
        ch, col = ("●", PINK_H) if k < 3 else (("•", PINK) if k < 9 else ("·", LINE))
        cv.put(px, py, ch, col)
    reading = g is not None and t < len(g["lines"]) * 2 + 16
    names = ["mushroom", "antennal", "optic", "central", "motor"]
    fi = min(4, max(0, (t - 12) // 3)) if g else -1
    for i, n in enumerate(names):
        ry = gy - 4 + i
        got = g is not None and t > 10 + i
        cursor = reading and i == fi and t > 12
        if cursor:
            cv.text(gx - 10, ry, "▸", PINK_H)
        if n == "motor":
            cv.text(gx - 8, ry, "motor", GREY_L if got else DIM)
            cv.text(gx + 3, ry, g["verdict"].lower() if got else "", BONE)
            continue
        v = vals.get(n, 0)
        bad = n == "antennal" and v < DIRTY
        cv.text(gx - 8, ry, n, (RED if bad else GREY_L) if got else DIM)
        if got:
            cv.text(gx + 3, ry, "%.2f" % v, RED if bad else BONE)
    if g and g["decision"] and not reading:
        d = g["decision"][0]
        col = GREEN if d == "ENTER" else (RED if d == "SKIP" else AMBER)
        cv.text(gx - len(d) // 2, gy + 3, d, BOLD + col)
        if d == "WAIT":
            frac = (s.f % s.cycle) / s.cycle
            n8 = int(frac * 8)
            cv.text(gx - 5, gy + 4, "▕" + "█" * n8 + "·" * (8 - n8) + "▏", AMBER)
    elif reading and g:
        cv.text(gx - 4, gy + 3, "reading", PINK_D)
    cv.text(gx - 2, gy + 11, "grok", BOLD + PINK)
    cv.text(gx - 8, gy + 12, "simulated reader", GREY)
    # ------------------------------------------------------------ the two lanes between the heads
    x0, x1 = bx + 16, gx - 16
    cv.text(x0, by - 3, "·" * (x1 - x0), DIM)
    cv.put(x1, by - 3, "▶", PINK_D)
    cv.text(x0, by + 3, "·" * (x1 - x0), DIM)
    cv.put(x0 - 1, by + 3, "◀", PINK_D)
    cv.text(x0, by - 5, "waggle vector", GREY)
    cv.text(x0, by + 5, "decision", GREY)
    if g:
        cols = []
        for n, v, _ in g["packet"]:
            cols.append(RED if (n == "antennal" and v < DIRTY) else (PINK_H if v >= 0.6 else PINK))
        cols.append(GREEN if g["verdict"] == "PASS" else BONE)
        span = x1 - x0
        if t <= 14:
            for j, c in enumerate(cols):
                u = min(1.0, max(0.0, t / 12 - j * 0.07))
                cv.put(x0 + int(u * (span - 1)), by - 3, "◆", c)
        if g["decision"] and not reading:
            u = min(1.0, max(0.0, (t - len(g["lines"]) * 2 - 16) / 8))
            d = g["decision"][0]
            col = GREEN if d == "ENTER" else (RED if d == "SKIP" else AMBER)
            px = x1 - int(u * (span - 1)) - 1
            cv.text(max(x0, px - len(d) + 1), by + 3, d.lower(), BOLD + col)
    cv.text(x + 2, y + h - 2, "five fields go out, one decision comes back.", GREY)


def build_wide2(s, W, H):
    cv = Canvas(W, H)
    header(cv, s, W)
    top = 3
    lw = 82
    rw = W - lw - 3
    mw = (rw - 1) // 2
    panel_heads(cv, s, 1, top, lw, 31)
    panel_packet(cv, s, 1, top + 31, lw, H - top - 32)
    x2 = lw + 2
    x3 = x2 + mw + 1
    w3 = W - x3 - 1
    panel_grok(cv, s, x2, top, mw, 20)
    panel_ledger(cv, s, x2, top + 20, mw, H - top - 21)
    panel_account(cv, s, x3, top, w3, 21)
    panel_stats(cv, s, x3, top + 21, w3, H - top - 22)
    cv.text(1, H - 1, "when the bee disagrees with itself, grok waits one cycle and reads again.", GREY)
    cv.rtext(W - 1, H - 1, "model assumption: rug odds rise with input noise. grok here is a rule based reader, not the api.", DIM)
    return cv


def build_compact2(s, W, H):
    cv = Canvas(W, H)
    header(cv, s, W)
    top = 3
    panel_heads(cv, s, 1, top, 82, 31)
    panel_packet(cv, s, 1, top + 31, 82, 17)
    panel_grok(cv, s, 1, top + 48, 82, 16)
    panel_stats(cv, s, 1, top + 64, 82, max(12, H - top - 65))
    return cv
