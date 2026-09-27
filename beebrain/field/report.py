"""
headless field runs and their reports.

  beebrain forage --chain solana --minutes 60 --out build/field-solana.json
  beebrain report build/field-solana.json

forage runs the same session as the page and the terminal, without drawing, and
writes a json snapshot every minute. report turns it into markdown: the forward
test per verdict, the race, what the reflexes caught, and which senses moved with
the 15 minute outcome.
"""
import json
import math
import time

from ..brain import FEATS
from .feed import Feed, now_ms
from .features import LIVE_LABELS
from .session import FWD_CAP, FieldSession

SCORE_FAST_S, SCORE_MID_S, SCORE_SLOW_S = 0.9, 1.6, 2.4
MARK_S = 2.0


def snapshot(s, started_ms, feed):
    return {
        "chain": s.chain, "started": started_ms, "now": now_ms(), "minutes": (now_ms() - started_ms) / 60000.0,
        "feed": {"calls": feed.calls, "errors": feed.errors, "status": feed.status},
        "scored": s.scored, "counts": s.counts, "reflexed": s.reflexed, "queue": len(s.queue),
        "forward": s.forward(), "pending": len(s.shadows), "dropped": s.fwd_dropped,
        "accounts": {k: a.stats() for k, a in s.accounts.items()},
        "closed": {k: a.closed for k, a in s.accounts.items()},
        "gate": s.gate(),
        "brain": {"sugar": s.brain.sugar, "pain": s.brain.pain, "eps": s.brain.eps, "resolved": s.brain.resolved},
        # the whole memory, so a run can seed the next bee: synapse weights and recent sparse codes
        "memory": s.to_json()["brain"],
        "log": s.fwd_log,
    }


def forage(chain="solana", minutes=60.0, out="field.json", horizon=None, say=print):
    s = FieldSession(chain) if horizon is None else FieldSession(chain, horizon_min=horizon)
    feed = Feed(chain)
    t0 = now_ms()
    end = time.time() + minutes * 60
    last = {"poll": 0.0, "score": 0.0, "mark": 0.0, "save": 0.0}
    while time.time() < end or s.shadows:
        t = time.time()
        if t - last["poll"] >= 3:
            last["poll"] = t
            new, fresh = feed.poll(t, s.tracked())
            s.ingest(new, now_ms())
            s.ingest(fresh, now_ms())
        # after the clock runs out, stop scoring and only let the pending forward tests land
        scoring = time.time() < end
        every = SCORE_FAST_S if len(s.queue) > 40 else SCORE_MID_S if len(s.queue) > 12 else SCORE_SLOW_S
        if scoring and s.queue and t - last["score"] >= every:
            last["score"] = t
            s.score_next(now_ms())
        if t - last["mark"] >= MARK_S:
            last["mark"] = t
            s.mark(now_ms())
        if t - last["save"] >= 60:
            last["save"] = t
            with open(out, "w") as fh:
                json.dump(snapshot(s, t0, feed), fh)
            fw = s.forward()
            say("%5.1f min  scored %d  fwd %d  bee $%.0f  random $%.0f  %s" % (
                (now_ms() - t0) / 60000, s.scored, sum(f["n"] for f in fw.values()),
                s.accounts["bee"].equity, s.accounts["random"].equity, feed.status))
        if time.time() > end + (s.horizon_min + 5) * 60:
            break
        time.sleep(0.2)
    with open(out, "w") as fh:
        json.dump(snapshot(s, t0, feed), fh)
    return s


# ------------------------------------------------------------------ report ---
def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0.0
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2.0
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 8:
        return None
    ra, rb = rank(a), rank(b)
    ma, mb = mean(ra), mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def cap(xs):
    return [min(x, FWD_CAP) for x in xs]


def pct(x, d=1):
    if x > FWD_CAP:
        return ">+%.0f%%" % (FWD_CAP * 100)
    return ("%+." + str(d) + "f%%") % (x * 100)


def report(d):
    log = d["log"]
    lines = []
    w = lines.append
    w("# beebrain field report · %s" % d["chain"])
    w("")
    w("%.0f minutes on live pools. %d pools scored, %d forward tested at +%s min, fees in. paper money only." % (
        d["minutes"], d["scored"], len(log), "15"))
    w("")
    w("averages cap each 15 minute return at +%.0f%%, so one dead pool that reprices a thousandfold cannot own a column. %d pools hit the cap." % (
        FWD_CAP * 100, sum(1 for r in log if r["net"] > FWD_CAP)))
    w("")
    w("## forward test")
    w("")
    w("| verdict | pools | hit rate | avg net | median net |")
    w("| --- | --- | --- | --- | --- |")
    groups = [(v, [r["net"] for r in log if r["verdict"] == v]) for v in ("PASS", "WATCH", "SKIP")]
    groups.append(("SKIP by the brain", [r["net"] for r in log if r["verdict"] == "SKIP" and not r["reasons"]]))
    for v, xs in groups:
        if xs:
            w("| %s | %d | %.0f%% | %s | %s |" % (v, len(xs), 100 * mean([x > 0 for x in xs]), pct(mean(cap(xs))), pct(median(xs))))
        else:
            w("| %s | 0 | - | - | - |" % v)
    brain_skip = [r["net"] for r in log if r["verdict"] == "SKIP" and not r["reasons"]]
    reflex = [r["net"] for r in log if r["reasons"]]
    reached = [r["net"] for r in log if not r["reasons"]]
    w("")
    w("## what the reflexes caught")
    w("")
    w("| group | pools | hit rate | avg net | median net |")
    w("| --- | --- | --- | --- | --- |")
    for name, xs in (("killed by a reflex", reflex), ("reached the lobes", reached), ("brain said SKIP", brain_skip)):
        if xs:
            w("| %s | %d | %.0f%% | %s | %s |" % (name, len(xs), 100 * mean([x > 0 for x in xs]), pct(mean(cap(xs))), pct(median(xs))))
    by = {}
    for r in log:
        for reason in r["reasons"] or []:
            by.setdefault(reason, []).append(r["net"])
    if by:
        w("")
        for reason, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
            w("- %s: %d pools, hit %.0f%%, median %s" % (reason, len(xs), 100 * mean([x > 0 for x in xs]), pct(median(xs))))
    w("")
    w("## the race")
    w("")
    w("| account | equity | return | trades | won | max drawdown |")
    w("| --- | --- | --- | --- | --- | --- |")
    for k in ("bee", "random", "you"):
        a = d["accounts"][k]
        w("| %s | $%.0f | %s | %d | %d | %.0f%% |" % (k, a["equity"], pct(a["equity"] / a["start"] - 1), a["trades"], a["wins"], a["max_drawdown"] * 100))
    w("")
    w("## which senses moved with the outcome")
    w("")
    w("spearman rank correlation between each live sense at scoring time and the 15 minute net return, pools that reached the lobes.")
    w("")
    w("| sense | rho |")
    w("| --- | --- |")
    rows = [r for r in log if not r["reasons"]]
    for f in FEATS:
        if f == "bundle":
            continue
        rho = spearman([r["obs"][f] for r in rows], [r["net"] for r in rows])
        w("| %s | %s |" % (LIVE_LABELS[f], "%+.2f" % rho if rho is not None else "-"))
    rho = spearman([r["comb"] for r in rows], [r["net"] for r in rows])
    w("| **bee score** | %s |" % ("%+.2f" % rho if rho is not None else "-"))
    w("")
    w("## gate")
    w("")
    p_ = [r["net"] for r in log if r["verdict"] == "PASS"]
    s_ = [r["net"] for r in log if r["verdict"] == "SKIP" and not r["reasons"]]
    edge = mean(cap(p_)) - mean(cap(s_)) if p_ and s_ else 0.0
    bee, rnd = d["accounts"]["bee"]["equity"], d["accounts"]["random"]["equity"]
    w("- %s forward tested pools: %d of 300" % ("[x]" if len(log) >= 300 else "[ ]", len(log)))
    w("- %s PASS beats the brain's SKIP by 5 points: %s" % ("[x]" if edge >= 0.05 else "[ ]", pct(edge)))
    w("- %s bee beats random: $%.0f vs $%.0f" % ("[x]" if bee > rnd else "[ ]", bee, rnd))
    w("")
    w("brain: %d sugar, %d punishment, explore %.0f%%. feed: %d calls, %d errors." % (
        d["brain"]["sugar"], d["brain"]["pain"], d["brain"]["eps"] * 100, d["feed"]["calls"], d["feed"]["errors"]))
    top = sorted([r for r in log if r["net"] <= FWD_CAP], key=lambda r: -r["net"])[:5]
    low = sorted(log, key=lambda r: r["net"])[:5]
    if top:
        w("")
        w("best 15 minutes, under the cap: " + ", ".join("$%s %s (%s)" % (r["symbol"], pct(r["net"], 0), r["verdict"].lower()) for r in top))
        w("worst 15 minutes: " + ", ".join("$%s %s (%s)" % (r["symbol"], pct(r["net"], 0), r["verdict"].lower()) for r in low))
    return "\n".join(lines) + "\n"
