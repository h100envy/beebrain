"""ansi canvas, palette and small text helpers. stdlib only."""
from ..brain import clamp
from ..engine import money  # noqa: F401  re-exported for the panels

ESC = "\x1b["
BG = ESC + "48;5;16m"
OFF = ESC + "0m" + BG
BOLD = ESC + "1m"
PINK = ESC + "38;5;205m"
PINK_H = ESC + "38;5;218m"
PINK_D = ESC + "38;5;162m"
PINK_X = ESC + "38;5;89m"
LINE = ESC + "38;5;89m"
GREY = ESC + "38;5;244m"
GREY_L = ESC + "38;5;250m"
DIM = ESC + "38;5;237m"
BONE = ESC + "38;5;230m"
GREEN = ESC + "38;5;42m"
RED = ESC + "38;5;196m"
AMBER = ESC + "38;5;214m"
TG = ESC + "38;5;39m"          # the new sense gets its own colour
TG_D = ESC + "38;5;25m"

# telegram lab look
NAVY = ESC + "48;5;235m"
BLUE = ESC + "38;5;75m"
BLUE_D = ESC + "38;5;31m"
BLUE_X = ESC + "38;5;24m"
WHITE = ESC + "38;5;231m"
BAR = ESC + "48;5;25m" + ESC + "38;5;231m"
PILL = ESC + "48;5;75m" + ESC + "38;5;235m"

# the engine logs tones, the terminal paints them
TONE = {"dim": GREY, "text": GREY_L, "entry": BONE, "good": GREEN, "bad": RED, "wait": AMBER, "tg": TG}


def tone(t):
    return TONE.get(t, GREY)


class Canvas:
    def __init__(self, w, h, bg=None):
        self.w, self.h = w, h
        self.bg = bg or BG
        self.ch = [[" "] * w for _ in range(h)]
        self.co = [[""] * w for _ in range(h)]

    def put(self, x, y, c, col=""):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.ch[y][x] = c
            self.co[y][x] = col

    def text(self, x, y, s, col=""):
        for i, c in enumerate(s):
            self.put(x + i, y, c, col)

    def rtext(self, xr, y, s, col=""):
        self.text(xr - len(s), y, s, col)

    def hbar(self, x, y, w, frac, col, full="█", empty="·"):
        n = int(round(clamp(frac) * max(0, w)))
        self.text(x, y, full * n, col)
        self.text(x + n, y, empty * (max(0, w) - n), DIM)

    def box(self, x, y, w, h, title="", sub=""):
        self.text(x, y, "┌" + "─" * (w - 2) + "┐", LINE)
        for r in range(1, h - 1):
            self.put(x, y + r, "│", LINE)
            self.put(x + w - 1, y + r, "│", LINE)
        self.text(x, y + h - 1, "└" + "─" * (w - 2) + "┘", LINE)
        if title:
            self.text(x + 2, y, " " + title + " ", BOLD + PINK)
            if sub:
                self.text(x + 5 + len(title), y, " " + sub + " ", GREY)

    def render(self):
        out = []
        for y in range(self.h):
            row, cur = [], None
            for x in range(self.w):
                c = self.co[y][x]
                if c != cur:
                    row.append(ESC + "0m" + self.bg + c)
                    cur = c
                row.append(self.ch[y][x])
            out.append("".join(row) + ESC + "0m" + self.bg)
        return self.bg + "\n".join(out) + ESC + "0m"

    def plain(self):
        """the same frame without colour, one string per row"""
        return ["".join(r) for r in self.ch]


def rbox(cv, x, y, w, h, title="", sub="", col=None):
    col = col or BLUE_X
    cv.text(x, y, "╭" + "─" * (w - 2) + "╮", col)
    for r in range(1, h - 1):
        cv.put(x, y + r, "│", col)
        cv.put(x + w - 1, y + r, "│", col)
    cv.text(x, y + h - 1, "╰" + "─" * (w - 2) + "╯", col)
    if title:
        cv.text(x + 2, y, "[ " + title + " ]", BOLD + BLUE)
        if sub:
            cv.text(x + 6 + len(title), y, " " + sub + " ", GREY)


GLYPH = {
    "0": ["███", "█ █", "█ █", "█ █", "███"], "1": [" █ ", "██ ", " █ ", " █ ", "███"],
    "2": ["███", "  █", "███", "█  ", "███"], "3": ["███", "  █", "███", "  █", "███"],
    "4": ["█ █", "█ █", "███", "  █", "  █"], "5": ["███", "█  ", "███", "  █", "███"],
    "6": ["███", "█  ", "███", "█ █", "███"], "7": ["███", "  █", "  █", "  █", "  █"],
    "8": ["███", "█ █", "███", "█ █", "███"], "9": ["███", "█ █", "███", "  █", "███"],
    "$": ["▄█▄", "█▄ ", "▀█▄", " ▀█", "▀█▀"], ",": ["   ", "   ", "   ", " █ ", "█  "],
    " ": ["   "] * 5,
}


def big(cv, x, y, s, col, dbl=True):
    cx = x
    for chx in s:
        g = GLYPH.get(chx, GLYPH[" "])
        narrow = chx == ","
        for r in range(5):
            row = g[r][1:3] if narrow else g[r]
            cv.text(cx, y + r, "".join(c * 2 for c in row) if dbl else row, col)
        cx += (4 if narrow else 7) if dbl else (3 if narrow else 4)


def big_width(s, dbl=True):
    return sum(((4 if c == "," else 7) if dbl else (3 if c == "," else 4)) for c in s)


def spark(vals, lo=None, hi=None):
    ticks = "▁▂▃▄▅▆▇█"
    if not vals:
        return ""
    lo = min(vals) if lo is None else lo
    hi = max(vals) if hi is None else hi
    return "".join(ticks[int(clamp((v - lo) / max(1e-9, hi - lo)) * 7)] for v in vals)


def line_pts(a, b):
    (x0, y0), (x1, y1) = a, b
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    pts = []
    for i in range(n + 1):
        p = (round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n))
        if not pts or pts[-1] != p:
            pts.append(p)
    return pts
