"""
real pools, turned into what the eight glomeruli smell.

the brain is the same one the sim trains. only the senses change. every live
feature sits in the slot of the synthetic feature it stands in for, so the
wiring, the sparse code and the thresholds do not move:

  slot          live meaning        source
  liquidity     liquidity           pool reserve in usd, log scale, $1k to $1m
  holders       buys                buy transactions in the last hour, log scale
  snipers       sell pressure       sells / (buys + sells) in the last 5 minutes
  bundle        reflex              1 when a reflex trips, see REFLEX below. always SKIP
  creator age   pool age            minutes since the pair was created, log scale, 3 days = 1
  heat          heat                rank of this pool's hourly volume in the current field
  accel         acceleration        5 minute volume pace against the hour, and 5 minute price move
  volume        turnover            hourly volume / liquidity, log scale

pool noise, which the antennal lobes measure, is thin data: few trades, few signals.

these are proxies. none of them is the hidden edge of the sim. whether any of
them carries an edge on a real chain is exactly what the forward test measures.
"""
import math

from ..brain import clamp

LIVE_LABELS = {
    "liquidity": "liquidity", "holders": "buys 1h", "snipers": "sell pressure", "bundle": "reflex",
    "creator age": "pool age", "heat": "heat", "accel": "acceleration", "volume": "turnover",
}

# reflex layer: deterministic kills before the brain, like nerve's reflexes
REFLEX_MIN_LIQ = 2000.0          # usd
REFLEX_FDV_LIQ = 250.0           # fdv this many times liquidity
REFLEX_HONEYPOT_BUYS = 25        # this many buys in an hour and not one sell
REFLEX_DUMP_M5 = -50.0           # percent in 5 minutes
REFLEX_RUG_H1 = -80.0            # percent in an hour

AGE_FULL_MIN = 4320.0            # 3 days


def num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def norm_dexscreener(p):
    """one pair from the dexscreener api, as a flat snapshot"""
    tx = p.get("txns") or {}
    vol = p.get("volume") or {}
    chg = p.get("priceChange") or {}
    base = p.get("baseToken") or {}
    return {
        "chain": p.get("chainId", ""),
        "pair": p.get("pairAddress", ""),
        "token": base.get("address", ""),
        "symbol": (base.get("symbol") or "?")[:12],
        "name": (base.get("name") or "")[:40],
        "dex": p.get("dexId", ""),
        "url": p.get("url", ""),
        "price": num(p.get("priceUsd")),
        "liq": num((p.get("liquidity") or {}).get("usd")),
        "fdv": num(p.get("fdv")),
        "created_ms": num(p.get("pairCreatedAt")),
        "buys_m5": num((tx.get("m5") or {}).get("buys")),
        "sells_m5": num((tx.get("m5") or {}).get("sells")),
        "buys_h1": num((tx.get("h1") or {}).get("buys")),
        "sells_h1": num((tx.get("h1") or {}).get("sells")),
        "vol_m5": num(vol.get("m5")),
        "vol_h1": num(vol.get("h1")),
        "chg_m5": num(chg.get("m5")),
        "chg_h1": num(chg.get("h1")),
        "src": "dexscreener",
    }


def iso_ms(s):
    # 2026-09-26T11:29:33Z, without datetime so the browser twin can do the same with Date.parse
    import calendar
    import time
    try:
        return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")) * 1000.0
    except (TypeError, ValueError):
        return 0.0


def norm_gecko(p, chain, tokens=None):
    """one pool from the geckoterminal api, as a flat snapshot"""
    a = p.get("attributes") or {}
    tx = a.get("transactions") or {}
    vol = a.get("volume_usd") or {}
    chg = a.get("price_change_percentage") or {}
    name = a.get("name") or ""
    bid = (((p.get("relationships") or {}).get("base_token") or {}).get("data") or {}).get("id", "")
    tok = (tokens or {}).get(bid, {})
    addr = a.get("address", "")
    return {
        "chain": chain,
        "pair": addr,
        "token": tok.get("address", bid.split("_", 1)[-1]),
        "symbol": (tok.get("symbol") or name.split(" / ")[0] or "?")[:12],
        "name": (tok.get("name") or name)[:40],
        "dex": ((((p.get("relationships") or {}).get("dex") or {}).get("data") or {}).get("id", "")),
        "url": "https://dexscreener.com/%s/%s" % (chain, addr.lower()),
        "price": num(a.get("base_token_price_usd")),
        "liq": num(a.get("reserve_in_usd")),
        "fdv": num(a.get("fdv_usd")),
        "created_ms": iso_ms(a.get("pool_created_at") or ""),
        "buys_m5": num((tx.get("m5") or {}).get("buys")),
        "sells_m5": num((tx.get("m5") or {}).get("sells")),
        "buys_h1": num((tx.get("h1") or {}).get("buys")),
        "sells_h1": num((tx.get("h1") or {}).get("sells")),
        "vol_m5": num(vol.get("m5")),
        "vol_h1": num(vol.get("h1")),
        "chg_m5": num(chg.get("m5")),
        "chg_h1": num(chg.get("h1")),
        "src": "geckoterminal",
    }


def reflex(s):
    """reasons to skip without asking the brain. empty list means the pool reaches the lobes."""
    out = []
    if s["liq"] <= 0:
        out.append("no pool liquidity yet, bonding curve")
    elif s["liq"] < REFLEX_MIN_LIQ:
        out.append("thin liquidity")
    if s["liq"] > 0 and s["fdv"] / s["liq"] > REFLEX_FDV_LIQ:
        out.append("fdv far above liquidity")
    if s["buys_h1"] >= REFLEX_HONEYPOT_BUYS and s["sells_h1"] == 0:
        out.append("no sells, possible honeypot")
    if s["chg_m5"] <= REFLEX_DUMP_M5:
        out.append("dumping now")
    if s["chg_h1"] <= REFLEX_RUG_H1:
        out.append("rugged in the last hour")
    return out


def heat_rank(vol_h1, field_vols):
    """share of pools in the field with less hourly volume than this one"""
    if not field_vols:
        return 0.5
    below = sum(1 for v in field_vols if v < vol_h1)
    same = sum(1 for v in field_vols if v == vol_h1)
    return clamp((below + 0.5 * same) / len(field_vols))


def features(s, field_vols, now_ms):
    """returns (obs, noise, reflex reasons)"""
    liq = max(s["liq"], 1.0)
    age_min = max(0.0, (now_ms - s["created_ms"]) / 60000.0) if s["created_ms"] else 0.0
    m5 = s["buys_m5"] + s["sells_m5"]
    pace = s["vol_m5"] * 12.0 / max(s["vol_h1"], 1.0)
    reasons = reflex(s)
    obs = {
        "liquidity": clamp((math.log10(liq) - 3.0) / 3.0),
        "holders": clamp(math.log10(1.0 + s["buys_h1"]) / 3.3),
        "snipers": s["sells_m5"] / m5 if m5 >= 4 else 0.5,
        "bundle": 1.0 if reasons else 0.0,
        "creator age": clamp(math.log10(1.0 + age_min) / math.log10(1.0 + AGE_FULL_MIN)),
        "heat": heat_rank(s["vol_h1"], field_vols),
        "accel": clamp(0.5 * clamp(pace / 2.0) + 0.5 * clamp(0.5 + s["chg_m5"] / 40.0)),
        "volume": clamp(math.log10(1.0 + 10.0 * s["vol_h1"] / liq) / 2.0),
    }
    tx = s["buys_h1"] + s["sells_h1"]
    noise = clamp(1.0 - math.log10(1.0 + tx) / 3.0)
    return obs, noise, reasons


class FieldPool:
    """what brain.think expects: a name, observations and a noise level"""

    def __init__(self, snap, obs, noise, reasons, n):
        self.snap = snap
        self.id = n
        self.name = "$" + snap["symbol"].upper()
        self.addr = snap["pair"][:4] + "…" + snap["pair"][-4:] if len(snap["pair"]) > 8 else snap["pair"]
        self.obs = obs
        self.noise = noise
        self.reasons = reasons
