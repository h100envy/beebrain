"""
beebrain.live

LIVE ACCOUNT mode. reads your own closed trades from a csv and plays them back day by day
next to the brain animation. read only: it opens one local file and never talks to a chain.

csv columns: day,token,size_usd,pnl_pct
a header row, blank lines and rows whose first cell is not a number are ignored.

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import os

from .engine import POOLS_PER_DAY, money


def read_trades(path):
    out = []
    with open(path) as fh:
        for ln in fh:
            parts = [p.strip() for p in ln.split(",")]
            if len(parts) < 4 or not parts[0].replace(".", "").isdigit():
                continue
            out.append((float(parts[0]), parts[1], float(parts[2]), float(parts[3])))
    out.sort(key=lambda t: t[0])
    return out


class Live:
    """your own closed trades: day,token,size_usd,pnl_pct"""

    def __init__(self, path, start):
        self.src = os.path.basename(path)
        self.start = start
        self.trades = read_trades(path)
        self.done = []
        self.equity = start
        self.hist = [start]
        self.peak = start
        self.max_dd = 0.0
        self.log = None

    def advance(self, n_pools):
        day = n_pools / POOLS_PER_DAY + 1
        while len(self.done) < len(self.trades) and self.trades[len(self.done)][0] <= day:
            t = self.trades[len(self.done)]
            self.done.append(t)
            pnl = t[2] * t[3] / 100
            self.equity += pnl
            self.hist.append(self.equity)
            self.peak = max(self.peak, self.equity)
            self.max_dd = min(self.max_dd, self.equity / self.peak - 1)
            if self.log is not None:
                self.log.append(("d%d" % int(t[0]) + " trade", "%s %+.0f%%  %s%s" % (
                    t[1], t[3], "+" if pnl >= 0 else "-", money(abs(pnl))), "good" if pnl >= 0 else "bad"))
