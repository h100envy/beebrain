"""stage 3: a ninth glomerulus for telegram velocity, and the telegram lab look."""
import math
import textwrap

from ..brain import FEATS, FEATS9, clamp
from ..market import AGE_OLD, VEL_HI
from .canvas import (AMBER, BAR, BLUE, BLUE_D, BLUE_X, BOLD, BONE, DIM, ESC, GREEN, GREY, GREY_L, LINE,
                     NAVY, PILL, PINK, PINK_D, PINK_H, PINK_X, RED, TG, TG_D, WHITE, Canvas, line_pts,
                     money, rbox, spark)
from .panels import header, panel_account


def panel_organ(cv, s, x, y, w, h):
    """stage 3 hero: one big antenna, the telegram room pouring into its tip, nine glomeruli at its base."""
    e = s.e
    cv.box(x, y, w, h, "NEW SENSE ORGAN", "a ninth glomerulus for telegram")
    k = s.f % s.cycle
    tg = e.tg
    vel = tg["vel"]
    # the telegram room on the right, messages drifting left into the antenna tip
    rx0 = x + 54
    cv.text(rx0, y + 2, "telegram, 340 groups", TG)
    for i, (grp, msg, v) in enumerate(list(e.chat)[-10:]):
        ry = y + 4 + i
        drift = max(0, 6 - (s.frame - i * 3) % 40 // 6)
        col = TG if v > VEL_HI else (TG_D if v > 0.4 else DIM)
        cv.text(rx0 + drift, ry, grp, GREY if v <= VEL_HI else TG_D)
        cv.text(rx0 + drift + 6, ry, msg[:w - 60 - drift], col)
    # the antenna: scape rising from the head, elbow, then the flagellum reaching right
    base = (x + 14, y + 20)
    elbow = (x + 20, y + 9)
    tip = (x + 51, y + 5)
    scape = line_pts(base, elbow)
    flag = line_pts(elbow, tip)
    for i, (px, py) in enumerate(scape):
        cv.put(px, py, "█" if i % 2 == 0 else "▓", ESC + "38;5;94m")
    for i, (px, py) in enumerate(flag):
        cv.put(px, py, "●" if i % 3 == 0 else "─", ESC + "38;5;136m" if i % 3 else AMBER)
    cv.put(tip[0] + 1, tip[1], "◉", TG)
    # pulses run from tip to base when the counters update
    path = list(reversed(flag)) + list(reversed(scape))
    for j in range(1 + int(vel * 4)):
        u = (k * 2 + j * 5) % len(path)
        px, py = path[u]
        cv.put(px, py, "◆", TG if vel > VEL_HI else PINK_H)
    # counters in the last ten seconds, sitting under the antenna
    cy = y + 12
    cv.text(x + 25, cy, "last 10 s", GREY)
    rows = [("new messages", tg["msgs"], 200), ("new members", tg["members"], 70),
            ("link shares", tg["links"], 18), ("emoji ratio", tg["emoji"], 1.0)]
    for i, (lab, v, top) in enumerate(rows):
        ry = cy + 1 + i
        cv.text(x + 25, ry, lab, GREY_L)
        cv.hbar(x + 39, ry, 8, v / top, TG_D, "▇", "·")
        cv.rtext(x + 52, ry, ("%.2f" % v) if isinstance(v, float) else str(v), BONE)
    cv.text(x + 25, cy + 6, "velocity", BOLD + TG)
    cv.hbar(x + 35, cy + 6, 12, vel, TG if vel > VEL_HI else TG_D, "█", "·")
    cv.rtext(x + 52, cy + 6, "%.2f" % vel, BOLD + TG if vel > VEL_HI else BONE)
    # the antennal lobe: nine glomeruli, eight on-chain in pink, the ninth in telegram blue
    lx, ly = x + 13, y + 23
    pos = []
    for i in range(8):
        a = -math.pi / 2 + i / 8 * 2 * math.pi
        pos.append((round(lx + 9 * math.cos(a)), round(ly + 3.2 * math.sin(a))))
    obs = e.pool.obs if e.pool else {}
    for i, (px, py) in enumerate(pos):
        v = obs.get(FEATS[i], 0) if obs else 0
        col = PINK_H if v > 0.7 else (PINK if v > 0.45 else PINK_X)
        cv.text(px - 1, py, "(●)" if v > 0.45 else "(·)", col)
    glow = (s.frame // 3) % 2 == 0 and vel > VEL_HI
    cv.text(lx - 2, ly, "((◉))" if glow else " (◉) ", BOLD + TG if vel > VEL_HI else TG_D)
    cv.text(x + 2, ly + 4, "antennal lobe: 8 on-chain glomeruli + #9 telegram velocity", GREY)
    # from the lobe to the mushroom bodies
    cv.text(x + 27, ly, "──▶ mushroom bodies", PINK_D)
    mb = e.thought["lobes"]["mushroom"] if e.thought else 0
    cv.text(x + 47, ly, "%.2f" % mb, BOLD + PINK_H if mb > 0.6 else BONE)
    v = e.thought["verdict"] if e.thought else ""
    cv.text(x + 27, ly + 1, "──▶ motor", PINK_D)
    cv.text(x + 38, ly + 1, v, BOLD + (GREEN if v == "PASS" else (RED if v == "SKIP" else BONE)))
    cv.text(x + 2, y + h - 2, "the bee was never told what telegram is. velocity is just another number to it.", DIM)


def panel_matrix(cv, s, x, y, w, h):
    e = s.e
    cv.box(x, y, w, h, "CROSS-MODAL", "telegram x on-chain")
    cv.text(x + 2, y + 2, "velocity    creator    pools  wins", GREY)
    order = [((1, 1), "high", "old"), ((1, 0), "high", "new"), ((0, 1), "low", "old"), ((0, 0), "low", "new")]
    p = e.pool
    cur = (int(p.true["tg velocity"] > VEL_HI), int(p.true["creator age"] > AGE_OLD)) if p else None
    for i, (key, a, b) in enumerate(order):
        n, wn = e.cells[key]
        ry = y + 4 + i * 2
        rate = wn / n if n else 0
        on = key == cur
        cv.text(x + 2, ry, ("▸ " if on else "  ") + a, BOLD + TG if a == "high" else GREY_L)
        cv.text(x + 14, ry, b, BONE if b == "old" else GREY_L)
        cv.rtext(x + 31, ry, str(n), BONE)
        cv.rtext(x + 37, ry, str(wn), BONE)
        col = GREEN if rate >= 0.6 else (RED if rate < 0.4 else AMBER)
        cv.hbar(x + 3, ry + 1, w - 14, rate, col, "▇", "·")
        cv.rtext(x + w - 3, ry + 1, "%.0f%%" % (rate * 100) if n else "-", col)
    cv.text(x + 2, y + h - 2, "thresholds: velocity %.2f, creator age %.2f" % (VEL_HI, AGE_OLD), DIM)


def panel_surface(cv, s, x, y, w, h):
    e = s.e
    cv.box(x, y, w, h, "WHAT THE BEE LEARNED", "memory probe")
    cv.text(x + 2, y + 2, "memory response, other inputs at median", GREY)
    shades = "·░▒▓█"
    cv.text(x + 2, y + 4, "velocity", GREY)
    for i, vlab in enumerate(("0.92", "0.72", "0.45", "0.15")):
        row = 3 - i
        ry = y + 5 + i * 2
        cv.text(x + 4, ry, vlab, TG if row >= 2 else GREY_L)
        for j in range(4):
            v = e.surface[row][j]
            ch = shades[min(4, int(clamp((v - 0.3) / 0.45) * 4.99))]
            col = GREEN if v >= 0.62 else (PINK if v >= 0.48 else PINK_X)
            cv.text(x + 11 + j * 8, ry, ch * 6, col)
            cv.text(x + 11 + j * 8, ry + 1, " %.2f " % v, DIM)
    cv.text(x + 11, y + 13, "0.15    0.40    0.62    0.85", GREY_L)
    cv.text(x + 11, y + 14, "creator age", GREY)
    if w > 70:
        nx = x + 48
        notes = [("how to read it", GREY),
                 ("each cell asks the memory: a pool with", GREY_L),
                 ("this telegram velocity and this creator", GREY_L),
                 ("age, everything else average. print or rug?", GREY_L),
                 ("", GREY),
                 ("top right lighting up = the bee learned", PINK_H),
                 ("that a loud room pays only when the", PINK_H),
                 ("creator has a history.", PINK_H),
                 ("", GREY),
                 ("refreshed every 25 pools", DIM)]
        for i, (tx, col) in enumerate(notes):
            cv.text(nx, y + 4 + i, tx, col)
    hi_old, hi_new = e.surface[3][3], e.surface[3][0]
    cv.text(x + 2, y + h - 2, "loud room: old creator %.2f, new %.2f" % (hi_old, hi_new),
            GREEN if hi_old - hi_new > 0.1 else GREY)


def panel_catches(cv, s, x, y, w, h):
    e = s.e
    cv.box(x, y, w, h, "CAUGHT BEFORE CT", "loud telegram")
    cv.text(x + 2, y + 2, "pool          tg    age   mb    ct    result", GREY)
    rows = list(e.catches)[-(h - 4):]
    for i, (t, pid, name, vel, age, mb, lag, fin) in enumerate(reversed(rows)):
        ry = y + 3 + i
        cv.text(x + 2, ry, ("#%d %s" % (pid, name))[:13], BONE)
        cv.text(x + 16, ry, "%.2f" % vel, TG)
        cv.text(x + 22, ry, "%.2f" % age, BONE if age > AGE_OLD else GREY)
        cv.text(x + 28, ry, "%.2f" % mb, PINK)
        cv.text(x + 34, ry, "+%ds" % lag, GREY_L)
        cv.rtext(x + w - 3, ry, "%+.0f%%" % (fin * 100), GREEN if fin > 0 else RED)
    if not rows:
        cv.text(x + 2, y + 4, "no entry on high velocity yet. ct column is", GREY)
        cv.text(x + 2, y + 5, "how many seconds later the first post landed.", GREY)



def panel_telegram(cv, s, x, y, w, h):
    """a telegram group where the bee is a member and writes its own messages."""
    e = s.e
    cv.box(x, y, w, h, "TELEGRAM", "memecoin radar")
    # chat header like the app
    cv.text(x + 2, y + 1, "◉", TG)
    cv.text(x + 4, y + 1, "memecoin radar", BOLD + BONE)
    cv.rtext(x + w - 3, y + 1, "1,204 members", GREY)
    cv.text(x + 4, y + 2, "beebrain", PINK)
    cv.text(x + 13, y + 2, "bot · reads 340 groups", GREY)
    cv.text(x + 1, y + 3, "─" * (w - 2), LINE)
    # compose bubbles bottom up
    inner = w - 4
    bw = inner - 8
    blocks = []
    for m in list(e.room)[-30:]:
        lines = textwrap.wrap(m["text"], bw - 4) or [""]
        blocks.append((m, lines))
    if s.typing is not None:
        blocks.append(({"who": "beebrain", "bee": True, "typing": True, "time": ""}, []))
    bottom = y + h - 4
    yy = bottom
    for m, lines in reversed(blocks):
        if m.get("typing"):
            dots = "·" * (1 + (s.frame // 3) % 3)
            txt = "beebrain is typing " + dots
            cv.text(x + w - 3 - len(txt), yy, txt, TG)
            yy -= 2
            continue
        need = len(lines) + (3 if m["bee"] else 1)
        if yy - need < y + 4:
            break
        if m["bee"]:
            width = max(len(ln) for ln in lines) + 4
            width = max(width, 18)
            bx = x + w - 2 - width
            kind = m.get("kind", "info")
            edge = {"pass": GREEN, "win": GREEN, "loss": RED, "skip": AMBER, "insight": PINK_H, "ct": TG}.get(kind, TG)
            top_y = yy - len(lines) - 2
            cv.text(bx, top_y, "╭" + "─" * (width - 2) + "╮", edge)
            cv.text(bx + 2, top_y, " beebrain ", BOLD + PINK)
            cv.text(bx + 12, top_y, "bot ", GREY)
            for i, ln in enumerate(lines):
                cv.text(bx, top_y + 1 + i, "│", edge)
                cv.text(bx + 2, top_y + 1 + i, ln, BONE)
                cv.text(bx + width - 1, top_y + 1 + i, "│", edge)
            cv.text(bx, yy - 1, "╰" + "─" * (width - 2) + "╯", edge)
            cv.text(bx + width - 8, yy - 1, " " + m["time"] + " ", GREY)
            yy -= len(lines) + 3
        else:
            cv.text(x + 2, yy, m["who"], TG_D)
            cv.text(x + 3 + len(m["who"]), yy, lines[0][:inner - len(m["who"]) - 8], GREY_L)
            cv.rtext(x + w - 3, yy, m["time"], DIM)
            yy -= 1
    # input bar
    cv.text(x + 1, y + h - 3, "─" * (w - 2), LINE)
    cv.text(x + 2, y + h - 2, "write a message...", DIM)
    cv.rtext(x + w - 3, y + h - 2, "➤", TG)


def build_wide3(s, W, H):
    cv = Canvas(W, H)
    header(cv, s, W)
    top = 3
    lw = 82
    rw = W - lw - 3
    mw = (rw - 1) // 2
    panel_organ(cv, s, 1, top, lw, 31)
    panel_surface(cv, s, 1, top + 31, lw, H - top - 32)
    x2 = lw + 2
    x3 = x2 + mw + 1
    w3 = W - x3 - 1
    panel_telegram(cv, s, x2, top, mw, H - top - 1)
    panel_account(cv, s, x3, top, w3, 21)
    panel_matrix(cv, s, x3, top + 21, w3, 14)
    panel_catches(cv, s, x3, top + 35, w3, H - top - 36)
    cv.text(1, H - 1, "i gave it a new sense. it found the edge by itself, and now it tells the room.", GREY)
    cv.rtext(W - 1, H - 1, "synthetic pools. the velocity x creator edge is planted in the sim.", DIM)
    return cv


def panel_lobes3(cv, s, x, y, w, h):
    e = s.e
    cv.box(x, y, w, h, "NINE INPUTS", "this pool")
    obs = e.pool.obs if e.pool else {}
    for i, f in enumerate(FEATS9):
        ry = y + 2 + i
        if ry >= y + h - 1:
            break
        v = obs.get(f, 0)
        new = f == "tg velocity"
        cv.text(x + 2, ry, f, BOLD + TG if new else GREY_L)
        if f == "bundle":
            cv.text(x + 16, ry, "yes" if v > .5 else "no", RED if v > .5 else GREY_L)
            continue
        cv.hbar(x + 16, ry, w - 25, v, TG if new else PINK_D, "▇", "·")
        cv.rtext(x + w - 3, ry, "%.2f" % v, BONE)


def build_compact3(s, W, H):
    cv = Canvas(W, H)
    header(cv, s, W)
    top = 3
    panel_organ(cv, s, 1, top, 82, 31)
    panel_telegram(cv, s, 1, top + 31, 82, 30)
    panel_matrix(cv, s, 1, top + 61, 82, max(14, H - top - 62))
    return cv


def lab_bigbrain(cv, s, x, y, w, h):
    rbox(cv, x, y, w, h, "bee brain", "3d, %s points, rotating" % "{:,}".format(len(s.big.P)))
    b = s.big
    yaw = 0.55 * math.sin(s.frame * 0.02) + 0.25
    b.draw(cv, x + 2, y + 1, w - 4, h - 3, yaw)
    e = s.e
    p = e.pool
    vel = p.obs["tg velocity"] if p else 0
    lab = [("optic lobes", BLUE_D), ("mushroom bodies", PINK), ("central complex", ESC + "38;5;183m"),
           ("antennal lobes", ESC + "38;5;69m"), ("glomerulus 9, telegram", ESC + "38;5;45m"), ("motor", RED)]
    xx = x + 2
    for name, col in lab:
        on = (s.stage in name) or (name.startswith("glomerulus") and vel > VEL_HI)
        cv.text(xx, y + h - 2, name, BOLD + col if on else col)
        xx += len(name) + 3


def lab_topbar(cv, s, W):
    e = s.e
    cv.text(0, 0, " " * W, BAR)
    cv.text(1, 0, "beebrain", BAR + BOLD)
    cv.text(10, 0, "telegram lab", BAR)
    x = 26
    for i, name in enumerate(("brain", "grok", "telegram", "jev", "router", "arena")):
        lab = " %d %s " % (i + 1, name)
        cv.text(x, 0, lab, PILL + BOLD if i == 2 else BAR)
        x += len(lab) + 1
    eq = e.equity
    tick = "acct %s  %+.0f%%   trades %d   pool #%d   %s" % (money(eq), (eq / e.start - 1) * 100, len(e.closed), e.n, e.stamp())
    cv.rtext(W - 1, 0, tick, BAR)


def lab_scope(cv, s, x, y, w, h):
    lab = s.lab
    rbox(cv, x, y, w, h, "oscilloscope", "glomerulus 9, telegram velocity, membrane potential")
    rows = h - 3
    tr = list(lab.trace)[-(w - 12):]
    thr_row = y + 2 + int((1 - 1.0 / 1.3) * (rows - 1))
    cv.text(x + 2, thr_row, "thr", GREY)
    for i in range(w - 12):
        cv.put(x + 7 + i, thr_row, "┄", BLUE_X)
    cv.text(x + 2, y + 1 + rows, "rest", DIM)
    for i, v in enumerate(tr):
        cx = x + 7 + i
        if v > 1.2:                              # a spike: full height line
            for r in range(rows):
                cv.put(cx, y + 2 + r, "│" if r else "▲", WHITE if r == 0 else BLUE)
        else:
            r = int((1 - clamp((v + 0.2) / 1.5)) * (rows - 1))
            cv.put(cx, y + 2 + r, "•", BLUE)
    vel = s.e.pool.obs["tg velocity"] if s.e.pool else 0
    cv.rtext(x + w - 3, y + 1, "input %.2f   firing %s" % (vel, "fast" if vel > VEL_HI else "slow"), BLUE if vel > VEL_HI else GREY)


def lab_raster(cv, s, x, y, w, h):
    lab = s.lab
    rbox(cv, x, y, w, h, "spike raster", "every neuron, last 90 ticks")
    labels = [(f[:9], lab.spk[i], PINK) for i, f in enumerate(FEATS)] + [("tg vel", lab.spk[8], BLUE)]
    labels += [("kc %04d" % k, lab.kc_spk[j], PINK_D) for j, k in enumerate(lab.kc_show)]
    labels += [("x loud+old", lab.kc_spk[8], GREEN), ("x loud+new", lab.kc_spk[9], AMBER),
               ("x quiet+old", lab.kc_spk[10], BLUE_D), ("x quiet+new", lab.kc_spk[11], BLUE_D)]
    labels += [("mbon print", lab.mbon[0], GREEN), ("mbon rug", lab.mbon[1], RED)]
    span = w - 16
    groups = {0: "glomeruli", 9: "kenyon cells", 17: "cross-modal kenyon cells", 21: "output neurons"}
    ry = y + 1
    for i, (name, hist, col) in enumerate(labels):
        if i in groups:
            if ry >= y + h - 1:
                break
            cv.text(x + 2, ry, groups[i], GREY)
            ry += 1
        if ry >= y + h - 1:
            break
        cv.text(x + 2, ry, name[:12], col if name.startswith(("tg", "x ", "mbon")) else GREY_L)
        hs = list(hist)[-span:]
        line = "".join("|" if b else " " for b in hs)
        cv.text(x + 14, ry, line, col)
        ry += 1


def lab_kcgrid(cv, s, x, y, w, h):
    lab = s.lab
    cols = w - 4
    n = min(1000, cols * (h - 3))
    rbox(cv, x, y, w, h, "kenyon layer", "%d of 2,000 cells" % n)
    lit = 0
    for i in range(n):
        r, c = divmod(i, cols)
        g = lab.kc_glow[i]
        if g > 0.7:
            ch, col = "■", WHITE
            lit += 1
        elif g > 0.35:
            ch, col = "▪", PINK
        elif g > 0.1:
            ch, col = "·", PINK_D
        else:
            ch, col = "·", ESC + "38;5;238m"
        cv.put(x + 2 + c, y + 1 + r, ch, col)
    cv.text(x + 2, y + h - 2, "lit %d of %d, the sparse code keeps it near 5%%" % (lit, n), GREY)


def lab_reward(cv, s, x, y, w, h):
    lab = s.lab
    rbox(cv, x, y, w, h, "what the output learned", "memory probe over time")
    pts_o = [v for _, v in lab.curve_old]
    pts_n = [v for _, v in lab.curve_new]
    span = w - 26
    cv.text(x + 2, y + 2, "loud + old", GREEN)
    cv.text(x + 14, y + 2, spark(pts_o[-span:], 0, 1), GREEN)
    cv.rtext(x + w - 3, y + 2, "%.2f" % (pts_o[-1] if pts_o else 0.5), GREEN)
    cv.text(x + 2, y + 3, "loud + new", AMBER)
    cv.text(x + 14, y + 3, spark(pts_n[-span:], 0, 1), AMBER)
    cv.rtext(x + w - 3, y + 3, "%.2f" % (pts_n[-1] if pts_n else 0.5), AMBER)
    gap = (pts_o[-1] - pts_n[-1]) if pts_o else 0
    cv.text(x + 2, y + 5, "gap", GREY)
    cv.hbar(x + 14, y + 5, span, clamp(gap), BLUE, "█", "·")
    cv.rtext(x + w - 3, y + 5, "%+.2f" % gap, BLUE)
    col = lab.reward_col if lab.reward > 0.15 else DIM
    cv.text(x + 2, y + 6, "reward channel", GREY)
    cv.text(x + 18, y + 6, "▮" * int(lab.reward * (w - 22)), col)


def reround(cv, x, y, w, h, title, sub=""):
    """repaint a panel's frame in the lab style"""
    for r in range(1, h - 1):
        cv.put(x, y + r, "│", BLUE_X)
        cv.put(x + w - 1, y + r, "│", BLUE_X)
    cv.text(x, y, "╭" + "─" * (w - 2) + "╮", BLUE_X)
    cv.text(x, y + h - 1, "╰" + "─" * (w - 2) + "╯", BLUE_X)
    cv.text(x + 2, y, "[ " + title + " ]", BOLD + BLUE)
    if sub:
        cv.text(x + 6 + len(title), y, " " + sub + " ", GREY)


def lab_chat(cv, s, x, y, w, h):
    # the telegram chat, restyled for the lab: rounded, blue, bubbles on navy
    panel_telegram(cv, s, x, y, w, h)
    for r in range(h):
        for cx in (x, x + w - 1):
            cv.put(cx, y + r, "│", BLUE_X)
    cv.text(x, y, "╭" + "─" * (w - 2) + "╮", BLUE_X)
    cv.text(x, y + h - 1, "╰" + "─" * (w - 2) + "╯", BLUE_X)
    cv.text(x + 2, y, "[ telegram ]", BOLD + BLUE)
    cv.text(x + 15, y, " memecoin radar ", GREY)


def lab_matrix(cv, s, x, y, w, h):
    e = s.e
    rbox(cv, x, y, w, h, "cross-modal tally", "all pools")
    order = [((1, 1), "loud + old"), ((1, 0), "loud + new"), ((0, 1), "quiet + old"), ((0, 0), "quiet + new")]
    for i, (key, lab) in enumerate(order):
        n, wn = e.cells[key]
        rate = wn / n if n else 0
        ry = y + 2 + i
        col = GREEN if rate >= 0.6 else (RED if rate < 0.4 else AMBER)
        cv.text(x + 2, ry, lab, BLUE if lab.startswith("loud") else GREY_L)
        cv.rtext(x + 22, ry, "%d/%d" % (wn, n), BONE)
        cv.hbar(x + 24, ry, w - 33, rate, col, "▇", "·")
        cv.rtext(x + w - 3, ry, "%.0f%%" % (rate * 100) if n else "-", col)


def lab_status(cv, s, W, H):
    e = s.e
    p = e.pool
    cv.text(0, H - 1, " " * W, BAR)
    if p:
        t = e.thought
        v = t["verdict"]
        txt = " pool #%d %s   tg %.2f   creator %.2f   mushroom %.2f   %s   stage %s" % (
            p.id, p.name, p.obs["tg velocity"], p.true["creator age"], t["lobes"]["mushroom"], v, s.stage)
        cv.text(0, H - 1, txt, BAR)
    cv.rtext(W - 1, H - 1, "sim, synthetic pools, planted edge ", BAR)


def build_wide3b(s, W, H):
    cv = Canvas(W, H, bg=NAVY)
    lab_topbar(cv, s, W)
    top = 2
    th = min(24, max(18, H - 31))
    bw = 100
    lab_bigbrain(cv, s, 1, top, bw, th)
    ox = bw + 2
    ow = W - ox - 1
    sh = th - 9
    lab_scope(cv, s, ox, top, ow, sh)
    lab_reward(cv, s, ox, top + sh, ow, 9)
    y2 = top + th
    hh = H - y2 - 1
    cw = 50
    lab_chat(cv, s, 1, y2, cw, hh)
    rx = cw + 2
    rw = 72
    lab_raster(cv, s, rx, y2, rw, hh)
    x3 = rx + rw + 1
    w3 = W - x3 - 1
    kh = max(6, hh - 7 - 9)
    lab_kcgrid(cv, s, x3, y2, w3, kh)
    lab_matrix(cv, s, x3, y2 + kh, w3, 7)
    panel_catches(cv, s, x3, y2 + kh + 7, w3, hh - kh - 7)
    reround(cv, x3, y2 + kh + 7, w3, hh - kh - 7, "caught before ct", "loud telegram")
    lab_status(cv, s, W, H)
    return cv


def build_compact3b(s, W, H):
    cv = Canvas(W, H, bg=NAVY)
    lab_topbar(cv, s, W)
    lab_bigbrain(cv, s, 1, 2, W - 2, 22)
    lab_scope(cv, s, 1, 24, W - 2, 9)
    lab_chat(cv, s, 1, 33, W - 2, 26)
    lab_raster(cv, s, 1, 59, W - 2, H - 60)
    lab_status(cv, s, W, H)
    return cv
