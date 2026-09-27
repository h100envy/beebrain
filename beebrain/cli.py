"""
beebrain command line.

  beebrain terminal   the ansi terminal, every flag of the first build still works
  beebrain sim        headless runs, one line per seed
  beebrain render     3d video, stills and article figures, needs the optional extras

idea credited to the nerve protocol, github.com/h100envy/nerve
"""
import argparse
import json
import os
import subprocess
import sys

from . import __version__
from .engine import START_CASH, parse_seeds, run


def _terminal(a):
    from .terminal.app import run as run_terminal
    return run_terminal(post=a.post, layout=a.layout, speed=a.speed, seed=a.seed, trades=a.trades,
                        start=a.start, frames=a.frames, plain=a.plain, width=a.width, height=a.height)


def _sim(a):
    from .brain import waggle_vector
    from .engine import Engine
    seeds = parse_seeds(a.seeds)
    if a.vector:
        e = Engine(seeds[0])
        for _ in range(a.vector):
            e.step()
        print(json.dumps(waggle_vector(e.pool, e.thought), indent=2))
        return 0
    rows = [run(s, a.days, record=False).summary() for s in seeds]
    if a.json:
        print(json.dumps(rows, indent=2))
        return 0
    print("sim · synthetic pools · paper account from $%s · fees in · %g days x 40 pools" % (
        "{:,.0f}".format(START_CASH), a.days))
    print("%-6s %10s %7s %5s %6s %7s" % ("seed", "final", "trades", "wins", "win%", "max dd"))
    for r in rows:
        print("%-6d %10s %7d %5d %5.0f%% %6.0f%%" % (
            r["seed"], "${:,.0f}".format(r["final"]), r["trades"], r["wins"], r["win_rate"] * 100,
            r["max_drawdown"] * 100))
    if len(rows) > 1:
        up = sum(1 for r in rows if r["final"] > r["start"])
        print("%d of %d seeds above the start. the edge in these pools was planted." % (up, len(rows)))
    return 0


def _trade(a):
    from .terminal.field import run as run_field
    return run_field(chain=a.chain, layout=a.layout, fresh=a.fresh, frames=a.frames, plain=a.plain,
                     width=a.width, height=a.height, save=not a.no_save)


def _scan(a):
    import time
    from .field.feed import Feed, now_ms
    from .terminal.field import load_session
    s = load_session(a.chain)
    feed = Feed(a.chain)
    new, _ = feed.poll(time.time(), [])
    if not new:
        sys.stderr.write("no pools: %s\n" % feed.status)
        return 1
    t = now_ms()
    s.ingest(new, t)
    rows = []
    while s.queue:
        r = s.score_next(t)
        if r:
            rows.append(r)
    order = {"PASS": 0, "WATCH": 1, "SKIP": 2}
    rows.sort(key=lambda r: (order[r["verdict"]], -r["comb"]))
    rows = rows[:a.limit]
    if a.json:
        print(json.dumps([{"symbol": r["symbol"], "pair": r["pair"], "url": r["url"], "price": r["price"], "liq": r["liq"],
                           "verdict": r["verdict"], "score": round(r["comb"], 3), "reflex": r["reasons"],
                           "waggle": r["vector"]} for r in rows], indent=2))
        return 0
    print("beebrain scan · %s · %d pools · read only data · paper brain, not advice" % (a.chain, len(rows)))
    print("%-12s %-6s %6s %9s  %s" % ("pool", "verdict", "score", "liquidity", "why / link"))
    for r in rows:
        why = r["reasons"][0] if r["reasons"] else r["url"]
        print("%-12s %-6s %6.2f %9s  %s" % (("$" + r["symbol"])[:12], r["verdict"], r["comb"], "${:,.0f}".format(r["liq"]), why))
    return 0


def _bot(a):
    from .bot.app import BeeBot, read_token
    from .bot.telegram import Telegram
    try:
        token = read_token(a.token_file)
    except OSError:
        sys.stderr.write("no bot token. put the one @BotFather gave you in ~/.beebrain/bot.token (chmod 600) "
                         "or in BEEBRAIN_BOT_TOKEN\n")
        return 2
    chains = [c.strip() for c in a.chains.split(",") if c.strip()]
    BeeBot(Telegram(token), chains, channel=a.channel or None).run()
    return 0


def _forage(a):
    from .field.report import forage
    forage(a.chain, a.minutes, a.out, a.horizon)
    print("wrote", a.out, "· beebrain report", a.out)
    return 0


def _report(a):
    from .field.report import report
    import gzip
    opener = gzip.open if a.path.endswith(".gz") else open
    with opener(a.path, "rt") as fh:
        print(report(json.load(fh)), end="")
    return 0


RENDER = {
    "video": ("render/video.py", ["numpy", "scipy", "PIL"]),
    "stills": ("render/stills.py", ["numpy", "scipy", "PIL"]),
    "figures": ("brand/figs.py", ["numpy", "scipy", "PIL", "playwright"]),
}


def _render(a):
    import importlib.util
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script, mods = RENDER[a.what]
    missing = [m for m in mods if importlib.util.find_spec(m) is None]
    if missing:
        sys.stderr.write("beebrain render %s needs %s. install the extras: pip install -e '.[render,figures]'\n"
                         % (a.what, ", ".join(missing)))
        if "playwright" in missing:
            sys.stderr.write("then fetch a browser once: python -m playwright install chromium\n")
        return 2
    path = os.path.join(root, script)
    if not os.path.exists(path):
        sys.stderr.write("render scripts live in the repo, not the wheel. run this from a clone of "
                         "github.com/h100envy/beebrain\n")
        return 2
    return subprocess.call([sys.executable, path] + a.args, cwd=root)


def build_parser():
    ap = argparse.ArgumentParser(prog="beebrain", description="a honeybee brain, simulated, scoring memecoin pools inside nerve.")
    ap.add_argument("--version", action="version", version="beebrain " + __version__)
    sub = ap.add_subparsers(dest="cmd")

    t = sub.add_parser("terminal", help="run the ansi terminal")
    t.add_argument("--post", type=int, choices=(1, 2, 3), default=1, help="stage: 1 brain, 2 grok, 3 telegram")
    t.add_argument("--trades", default="", help="csv of your own closed trades: day,token,size_usd,pnl_pct")
    t.add_argument("--start", type=float, default=START_CASH, help="starting balance for --trades")
    t.add_argument("--layout", choices=("auto", "wide", "compact"), default="auto")
    t.add_argument("--speed", type=float, default=1.0)
    t.add_argument("--seed", type=int, default=5)
    t.add_argument("--frames", type=int, default=0, help="stop after this many frames")
    t.add_argument("--plain", action="store_true", help="no animation, print the last frame and exit")
    t.add_argument("--width", type=int, default=0)
    t.add_argument("--height", type=int, default=0)
    t.set_defaults(fn=_terminal)

    s = sub.add_parser("sim", help="headless runs, one line per seed")
    s.add_argument("--days", type=float, default=9)
    s.add_argument("--seeds", default="0-9", help="0-9, or 1,4,7")
    s.add_argument("--json", action="store_true")
    s.add_argument("--vector", type=int, default=0, metavar="POOL",
                   help="print the waggle vector of pool number POOL on the first seed")
    s.set_defaults(fn=_sim)

    tr = sub.add_parser("trade", help="paper trade real pools next to the bee, live, in the terminal")
    tr.add_argument("--chain", default="solana", choices=("solana", "base", "bsc", "robinhood"))
    tr.add_argument("--layout", choices=("auto", "wide", "compact"), default="auto")
    tr.add_argument("--fresh", action="store_true", help="start a new bee instead of the saved one")
    tr.add_argument("--no-save", action="store_true", help="do not read or write ~/.beebrain")
    tr.add_argument("--frames", type=int, default=0)
    tr.add_argument("--plain", action="store_true")
    tr.add_argument("--width", type=int, default=0)
    tr.add_argument("--height", type=int, default=0)
    tr.set_defaults(fn=_trade)

    sc = sub.add_parser("scan", help="score the live field once and print it")
    sc.add_argument("--chain", default="solana", choices=("solana", "base", "bsc", "robinhood"))
    sc.add_argument("--limit", type=int, default=25)
    sc.add_argument("--json", action="store_true")
    sc.set_defaults(fn=_scan)

    bt = sub.add_parser("bot", help="run the telegram bot: live verdicts, alerts, paper accounts per user")
    bt.add_argument("--chains", default="solana", help="comma list: solana,base,bsc,robinhood")
    bt.add_argument("--token-file", default=None, help="default ~/.beebrain/bot.token, or set BEEBRAIN_BOT_TOKEN")
    bt.add_argument("--channel", default="", help="also post every PASS to this channel, e.g. @yourchannel")
    bt.set_defaults(fn=_bot)

    fo = sub.add_parser("forage", help="run the field headless for a while and save a report")
    fo.add_argument("--chain", default="solana", choices=("solana", "base", "bsc", "robinhood"))
    fo.add_argument("--minutes", type=float, default=60)
    fo.add_argument("--horizon", type=float, default=None, help="forward test minutes, default 15")
    fo.add_argument("--out", default="field.json")
    fo.set_defaults(fn=_forage)

    rp = sub.add_parser("report", help="markdown summary of a forage run")
    rp.add_argument("path")
    rp.set_defaults(fn=_report)

    r = sub.add_parser("render", help="3d video, stills or article figures (optional extras)")
    r.add_argument("what", choices=sorted(RENDER))
    r.add_argument("args", nargs=argparse.REMAINDER, help="passed through to the script")
    r.set_defaults(fn=_render)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, "fn", None):
        # bare `beebrain` behaves like the first build: straight into the terminal
        a = ap.parse_args(["terminal"] + list(argv if argv is not None else sys.argv[1:]))
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
