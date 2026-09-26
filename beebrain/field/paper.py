"""
paper accounts on real prices.

a fill pays a 1% fee each way, the same 2% round trip the sim charges, plus price
impact from pool depth: buying `size` into a pool with `liq` usd of liquidity moves
the price by about 2 * size / liq. positions are marked at what they would fetch if
sold now, after impact and fee, so an open position never looks better than it is.

exits: take profit, stop loss, max hold, or a rug (liquidity collapses or price dies).
"""
FEE_SIDE = 0.01
IMPACT_MAX = 0.5
TAKE_PROFIT = 1.00             # +100%
STOP_LOSS = -0.35              # -35%
MAX_HOLD_MIN = 30.0
RUG_LIQ_DROP = 0.30            # liquidity below 30% of entry
RUG_PRICE = -0.90
START = 500.0


def impact(size, liq):
    if liq <= 0:
        return IMPACT_MAX
    return min(IMPACT_MAX, 2.0 * size / liq)


class Position:
    def __init__(self, pid, snap, size, t_ms, act=None, why=""):
        self.id = pid
        self.pair = snap["pair"]
        self.symbol = snap["symbol"]
        self.url = snap.get("url", "")
        self.size = size
        self.t0 = t_ms
        self.p0 = snap["price"]
        self.liq0 = snap["liq"]
        self.fill = snap["price"] * (1 + impact(size, snap["liq"]))
        self.qty = size * (1 - FEE_SIDE) / self.fill if self.fill > 0 else 0.0
        self.price = snap["price"]
        self.liq = snap["liq"]
        self.act = sorted(act) if act else []
        self.why = why
        self.peak = 0.0
        self.low = 0.0

    def value(self, price=None, liq=None):
        price = self.price if price is None else price
        liq = self.liq if liq is None else liq
        gross = self.qty * price
        return gross * (1 - impact(gross, liq)) * (1 - FEE_SIDE)

    def ret(self):
        return self.value() / self.size - 1 if self.size else 0.0

    def to_json(self):
        d = dict(self.__dict__)
        return d

    @classmethod
    def from_json(cls, d):
        p = cls.__new__(cls)
        p.__dict__.update(d)
        return p


class Account:
    def __init__(self, name, start=START):
        self.name = name
        self.start = start
        self.cash = start
        self.open = []
        self.closed = []            # dicts
        self.peak = start
        self.max_dd = 0.0
        self.seq = 0

    @property
    def equity(self):
        return self.cash + sum(p.value() for p in self.open)

    def buy(self, snap, size, t_ms, act=None, why=""):
        size = min(size, self.cash)
        if size < 1 or snap["price"] <= 0:
            return None
        self.seq += 1
        pos = Position("%s-%d" % (self.name, self.seq), snap, size, t_ms, act, why)
        self.cash -= size
        self.open.append(pos)
        return pos

    def close(self, pos, t_ms, reason):
        out = pos.value()
        self.cash += out
        self.open = [p for p in self.open if p is not pos]
        rec = {"id": pos.id, "pair": pos.pair, "symbol": pos.symbol, "size": pos.size, "out": out,
               "pnl": out - pos.size, "ret": out / pos.size - 1 if pos.size else 0.0,
               "t0": pos.t0, "t1": t_ms, "reason": reason, "act": pos.act, "url": pos.url}
        self.closed.append(rec)
        return rec

    def mark(self, snaps, t_ms, exits=True):
        """update prices from the latest snapshots, run the exit rules, return closed records"""
        done = []
        for pos in list(self.open):
            s = snaps.get(pos.pair)
            if s and s["price"] > 0:
                pos.price, pos.liq = s["price"], s["liq"]
            r = pos.ret()
            pos.peak, pos.low = max(pos.peak, r), min(pos.low, r)
            if not exits:
                continue
            held = (t_ms - pos.t0) / 60000.0
            move = pos.price / pos.p0 - 1 if pos.p0 else 0.0
            if pos.liq0 and pos.liq < pos.liq0 * RUG_LIQ_DROP or move <= RUG_PRICE:
                done.append(self.close(pos, t_ms, "rug"))
            elif r >= TAKE_PROFIT:
                done.append(self.close(pos, t_ms, "take profit"))
            elif r <= STOP_LOSS:
                done.append(self.close(pos, t_ms, "stop loss"))
            elif held >= MAX_HOLD_MIN:
                done.append(self.close(pos, t_ms, "max hold"))
        e = self.equity
        self.peak = max(self.peak, e)
        self.max_dd = min(self.max_dd, e / self.peak - 1 if self.peak else 0.0)
        return done

    def stats(self):
        n = len(self.closed)
        wins = sum(1 for c in self.closed if c["pnl"] > 0)
        return {"name": self.name, "equity": round(self.equity, 2), "start": self.start, "trades": n, "wins": wins,
                "win_rate": wins / n if n else 0.0, "open": len(self.open), "max_drawdown": self.max_dd}

    def to_json(self):
        return {"name": self.name, "start": self.start, "cash": self.cash, "open": [p.to_json() for p in self.open],
                "closed": self.closed[-500:], "peak": self.peak, "max_dd": self.max_dd, "seq": self.seq}

    @classmethod
    def from_json(cls, d):
        a = cls(d["name"], d["start"])
        a.cash, a.peak, a.max_dd, a.seq = d["cash"], d["peak"], d["max_dd"], d["seq"]
        a.open = [Position.from_json(p) for p in d["open"]]
        a.closed = d["closed"]
        return a
