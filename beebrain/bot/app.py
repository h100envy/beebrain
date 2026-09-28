"""
the beebrain telegram bot. the same field as /trade and `beebrain trade`: the bee scores
live pools, and every user gets a paper account of their own.

  beebrain bot --token-file ~/.beebrain/bot.token --chains solana,robinhood [--channel @yourchannel]

commands
  /start /help         what this is
  /scan                the best pools the bee scored in the last minutes
  <contract address>   paste any CA: the bee scores it on the spot
  /alerts on|off       a message for every PASS
  /buy <CA|$SYMBOL> <usd>, /sell <n>, /me      your paper account, $500 to start
  /race                you, the bee and random, plus the forward test and the gate
  /chain <name>        solana, base, bsc or robinhood

read only market data, paper money. no wallets, no keys, no orders.
"""
from datetime import datetime, timezone
import html
import json
import os
import re
import threading
import time

from ..field.feed import CHAINS, Feed, now_ms
from ..field.features import FieldPool, features
from ..field.paper import START, Account
from ..field.rng import FieldRng
from ..field.session import FieldSession, HISTORY_LIMIT
from .telegram import TelegramError

SCORE_EVERY_S = 1.5
MARK_EVERY_S = 3.0
SAVE_EVERY_S = 60.0
ALERT_GAP_S = 15.0
CMD_GAP_S = 0.8
MAX_BUY = 500.0
MENU_RETRY_S = 60.0
COMMANDS = [{"command": name, "description": description} for name, description in (
    ("start", "start here"), ("scan", "the best pools the bee scored"),
    ("history", "signal prices and outcomes, including losses"), ("status", "bot and market feed status"),
    ("race", "you vs the bee vs random"), ("me", "your paper account"),
    ("alerts", "on or off: a message for every PASS"), ("chain", "switch chain"),
    ("buy", "paper buy: contract address and amount"), ("sell", "close a paper position by number"),
    ("help", "commands and examples"))]
SITE = "https://beebrain.pro/trade/"

SOL_CA = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
EVM_CA = re.compile(r"^0x[0-9a-fA-F]{40}$")
DOT = {"PASS": "🟢", "WATCH": "🟡", "SKIP": "🔴"}


def esc(s):
    return html.escape(str(s), quote=False)


def usd(v):
    if v <= 0:
        return "curve"
    return "$%.1fm" % (v / 1e6) if v >= 1e6 else ("$%.0fk" % (v / 1e3) if v >= 1e3 else "$%.0f" % v)


def pct(x):
    return "%+.1f%%" % (x * 100)


def is_ca(s):
    return bool(SOL_CA.match(s) or EVM_CA.match(s))


class Field:
    """one chain: a shared bee, its feed and its lock"""

    def __init__(self, chain, state_dir, fetch=None):
        self.chain = chain
        self.path = os.path.join(state_dir, "bot-field-%s.json" % chain)
        self.s = self.load()
        self.feed = Feed(chain, fetch=fetch) if fetch else Feed(chain)
        self.lock = threading.RLock()
        self.t_score = self.t_mark = 0.0

    def load(self):
        try:
            with open(self.path) as fh:
                return FieldSession.from_json(json.load(fh))
        except (OSError, ValueError, KeyError):
            pass
        s = FieldSession(self.chain)
        # a fresh bot bee starts from the same seed the site uses, when the repo has one
        seed = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                            "web", "trade", "seed-%s.json" % self.chain)
        try:
            with open(seed) as fh:
                d = json.load(fh)
            s.seed_with(d["memory"], d["label"])
        except (OSError, ValueError, KeyError):
            pass
        return s

    def save(self):
        with self.lock:
            d = self.s.to_json()
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(d, fh)
        os.replace(tmp, self.path)


class BeeBot:
    def __init__(self, tg, chains=("solana",), state_dir=None, channel=None, fetch=None, clock=None):
        self.tg = tg
        self.state_dir = state_dir or os.path.join(os.path.expanduser("~"), ".beebrain")
        os.makedirs(self.state_dir, exist_ok=True)
        self.fields = {c: Field(c, self.state_dir, fetch) for c in chains}
        self.default = chains[0]
        self.channel = channel
        self.clock = clock or time.time
        self.path = os.path.join(self.state_dir, "bot.json")
        self.users, self.offset = {}, 0
        self.last_cmd, self.last_alert = {}, {}
        self.state_lock = threading.RLock()
        self.menu_ready = False
        self.started_at = time.time()
        self.last_poll_at = None
        self.field_ok_at = {}
        self.field_errors = {}
        self.load()

    # ------------------------------------------------------------- state
    def load(self):
        try:
            with open(self.path) as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            return
        self.offset = d.get("offset", 0)
        for uid, u in d.get("users", {}).items():
            self.users[uid] = {"chain": u.get("chain", self.default), "alerts": u.get("alerts", False),
                               "chat": u.get("chat"), "name": u.get("name", ""),
                               "acct": {c: Account.from_json(a) for c, a in u.get("acct", {}).items()}}

    def save(self):
        with self.state_lock:
            self._save()

    def _save(self):
        d = {"offset": self.offset, "users": {uid: {"chain": u["chain"], "alerts": u["alerts"], "chat": u["chat"], "name": u["name"],
                                                    "acct": {c: a.to_json() for c, a in u["acct"].items()}}
                                              for uid, u in self.users.items()}}
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(d, fh)
        os.replace(tmp, self.path)
        for f in self.fields.values():
            f.save()

    def user(self, frm, chat_id):
        uid = str(frm["id"])
        u = self.users.setdefault(uid, {"chain": self.default, "alerts": False, "chat": chat_id, "name": "", "acct": {}})
        u["chat"], u["name"] = chat_id, frm.get("username") or frm.get("first_name") or ""
        if u["chain"] not in self.fields:
            u["chain"] = self.default
        return u

    def account(self, u, chain=None):
        chain = chain or u["chain"]
        if chain not in u["acct"]:
            u["acct"][chain] = Account("you", START)
        return u["acct"][chain]

    # ------------------------------------------------------------- field
    def tracked(self, f):
        with self.state_lock, f.lock:
            out = f.s.tracked(25)
            for u in self.users.values():
                a = u["acct"].get(f.chain)
                for p in (a.open if a else []):
                    if p.pair not in out:
                        out.append(p.pair)
            return out[:30]

    def tick_field(self, f):
        """poll, score, mark. returns (new PASS records, closed user positions)"""
        t = self.clock()
        new, fresh = f.feed.poll(t, self.tracked(f))
        passes, closes = [], []
        with self.state_lock, f.lock:
            now = now_ms()
            f.s.ingest(new, now)
            f.s.ingest(fresh, now)
            if t - f.t_score >= SCORE_EVERY_S and f.s.queue:
                f.t_score = t
                r = f.s.score_next(now)
                if r and r["verdict"] == "PASS":
                    passes.append(r)
            if t - f.t_mark >= MARK_EVERY_S:
                f.t_mark = t
                f.s.mark(now)
                for uid, u in self.users.items():
                    a = u["acct"].get(f.chain)
                    if a:
                        for c in a.mark(f.s.field, now):
                            closes.append((u, c))
        return passes, closes

    def look(self, f, s):
        """score one pool without side effects: no trades, no forward test, the shared rng untouched"""
        with f.lock:
            vols = [x["vol_h1"] for x in f.s.field.values()] or [s["vol_h1"]]
            obs, noise, reasons = features(s, vols, now_ms())
            pool = FieldPool(s, obs, noise, reasons, 0)
            keep = f.s.brain.rng
            f.s.brain.rng = FieldRng(abs(hash(s["pair"])) & 0xFFFFFFFF)
            try:
                t = f.s.brain.think(pool, None)
            finally:
                f.s.brain.rng = keep
        return obs, noise, reasons, t

    def find(self, f, q):
        """a pool by CA, pair address or $SYMBOL: from the field, or fetched on demand"""
        q = q.strip()
        sym = q.lstrip("$").upper()
        with f.lock:
            for s in f.s.field.values():
                if q in (s["token"], s["pair"]) or ("$" in q and s["symbol"].upper() == sym):
                    return s
        if is_ca(q):
            found = f.feed.pairs_for_tokens([q])
            if not found:
                d = f.feed.refresh([q])
                found = d
            if found:
                s = max(found, key=lambda x: x["liq"])
                s = dict(s, t_ms=now_ms())
                with f.lock:
                    f.s.field[s["pair"]] = s
                return s
        return None

    # ----------------------------------------------------------- replies
    def card(self, f, s, obs, noise, reasons, t):
        v = t["verdict"]
        lines = ["%s <b>$%s</b> · %s · %s" % (DOT[v], esc(s["symbol"]), v, f.chain),
                 "<code>%s</code>" % esc(s["token"]),
                 "liq %s · 1h vol %s · 5m %s" % (usd(s["liq"]), usd(s["vol_h1"]), pct(s["chg_m5"] / 100)), ""]
        if reasons:
            lines.append("reflex: " + esc(", ".join(reasons)))
        else:
            L = t["lobes"]
            lines += ["mushroom %.2f · seen %d, printed %d" % (L["mushroom"], t["seen"], t["won"]),
                      "antennal %.2f · %s" % (L["antennal"], "noisy input" if L["antennal"] < 0.45 else "clean input"),
                      "optic %.2f · %s" % (L["optic"], "accelerating" if obs["accel"] > 0.55 else "flat"),
                      "central %.2f · consensus %.2f" % (L["central"], t["consensus"])]
        lines += ["", "<i>paper brain, uncalibrated. not advice.</i>"]
        buttons = [[{"text": "paper $25", "callback_data": "b:25:" + s["pair"][:52]},
                    {"text": "paper $50", "callback_data": "b:50:" + s["pair"][:52]}]]
        if s.get("url", "").startswith("https://dexscreener.com/"):
            buttons.append([{"text": "chart ↗", "url": s["url"]}, {"text": "race on the site ↗", "url": SITE}])
        return "\n".join(lines), buttons

    # ---------------------------------------------------------- commands
    def handle(self, upd):
        with self.state_lock:
            return self._handle(upd)

    def _handle(self, upd):
        if "callback_query" in upd:
            return self.on_callback(upd["callback_query"])
        m = upd.get("message") or {}
        text = (m.get("text") or "").strip()
        if not text or "from" not in m:
            return
        chat = m["chat"]["id"]
        u = self.user(m["from"], chat)
        t = self.clock()
        if t - self.last_cmd.get(chat, float("-inf")) < CMD_GAP_S:
            return
        self.last_cmd[chat] = t
        cmd, _, arg = text.partition(" ")
        cmd = cmd.split("@")[0].lower()
        f = self.fields[u["chain"]]
        if cmd in ("/start", "/help"):
            return self.tg.send(chat, self.help_text(u))
        if cmd == "/scan":
            return self.cmd_scan(chat, f)
        if cmd == "/history":
            return self.tg.send(chat, self.history_text(f, arg))
        if cmd == "/status":
            return self.tg.send(chat, self.status_text(f))
        if cmd == "/alerts":
            u["alerts"] = arg.strip().lower() != "off"
            return self.tg.send(chat, "alerts %s. %s" % ("on" if u["alerts"] else "off",
                                "a message for every PASS on %s, at most one every %d seconds." % (u["chain"], ALERT_GAP_S) if u["alerts"] else ""))
        if cmd == "/chain":
            c = arg.strip().lower()
            if c not in self.fields:
                return self.tg.send(chat, "chains here: " + ", ".join(self.fields))
            u["chain"] = c
            return self.tg.send(chat, "now on %s." % c)
        if cmd == "/me":
            return self.tg.send(chat, self.me_text(u))
        if cmd == "/race":
            return self.tg.send(chat, self.race_text(u, f), [[{"text": "open the field ↗", "url": SITE}]])
        if cmd == "/buy":
            parts = arg.split()
            if not parts:
                return self.tg.send(chat, "usage: /buy &lt;CA or $SYMBOL&gt; [usd]")
            amt = self.parse_usd(parts[1] if len(parts) > 1 else "50")
            return self.buy(chat, u, f, parts[0], amt)
        if cmd == "/sell":
            return self.sell(chat, u, f, arg.strip())
        if is_ca(text):
            s = self.find(f, text)
            if not s:
                return self.tg.send(chat, "no pool found for that address on %s. try /chain." % f.chain)
            body, buttons = self.card(f, s, *self.look(f, s))
            return self.tg.send(chat, body, buttons)
        return self.tg.send(chat, "paste a contract address, or try /scan, /race, /me, /alerts on.")

    @staticmethod
    def parse_usd(s):
        try:
            return max(1.0, min(MAX_BUY, float(s.lstrip("$"))))
        except ValueError:
            return 50.0

    def help_text(self, u):
        return ("🐝 <b>BeeBrain</b>\na honeybee brain, simulated, scoring live memecoin pools.\n\n"
                "paste any <b>contract address</b> and the bee scores it.\n"
                "/history  recent signals and their outcomes\n/status  bot and feed status\n"
                "/scan  the best pools right now\n/alerts on  a message for every PASS\n"
                "/buy &lt;CA&gt; 50  paper trade, you start with $500\n/sell 1  close a position\n/me  your paper account\n"
                "/race  you vs the bee vs random, and the forward test\n/chain %s\n\n"
                "<i>real prices, paper money. no wallets, no keys, no orders. not advice.</i>\nbeebrain.pro · @beebrainnerve"
                % " | ".join(self.fields))

    def cmd_scan(self, chat, f):
        with f.lock:
            rows = [r for r in list(f.s.recent)[-40:] if not r["reasons"]]
        if not rows:
            return self.tg.send(chat, "the bee is still flying out on %s. try again in a minute." % f.chain)
        rows.sort(key=lambda r: ({"PASS": 0, "WATCH": 1, "SKIP": 2}[r["verdict"]], -r["comb"]))
        lines = ["<b>the bee on %s</b>, pools that reached the lobes" % f.chain, ""]
        for r in rows[:8]:
            lines.append("%s <b>$%s</b> %.2f · liq %s\n<code>%s</code>" % (
                DOT[r["verdict"]], esc(r["symbol"]), r["comb"], usd(r["liq"]), esc(r.get("token", ""))))
        lines.append("\n<i>tap a CA to copy it. paste it back here for the full read.</i>")
        return self.tg.send(chat, "\n".join(lines))

    @staticmethod
    def utc(t_ms):
        if t_ms is None:
            return "unknown"
        return datetime.fromtimestamp(t_ms / 1000, timezone.utc).strftime("%m-%d %H:%M:%S UTC")

    def history_text(self, f, arg=""):
        args = arg.lower().split()
        verdict = "ALL"
        if args and args[0] in ("all", "pass", "watch", "skip"):
            verdict = args.pop(0).upper()
        try:
            page = int(args[0]) if len(args) == 1 else 1
            if len(args) > 1 or page < 1:
                raise ValueError
        except ValueError:
            return "usage: /history [all|pass|watch|skip] [page]"
        with f.lock:
            rows = [dict(r) for r in reversed(f.s.history) if verdict == "ALL" or r["verdict"] == verdict]
            fw = f.s.forward()
            pending, dropped = len(f.s.shadows), f.s.fwd_dropped
            horizon = f.s.horizon_min
        pages = max(1, (len(rows) + 4) // 5)
        if page > pages:
            return "history has %d pages. try /history %s %d" % (pages, verdict.lower(), pages)
        lines = ["<b>signal history</b> · %s · %s · page %d/%d" % (f.chain, verdict.lower(), page, pages),
                 "target +%g min · 2%% round-trip fee model · no slippage" % horizon,
                 "all-time: %d resolved · %d pending · %d unavailable" % (
                     sum(fw[v]["n"] for v in ("PASS", "WATCH", "SKIP")), pending, dropped)]
        if not rows:
            lines.append("no recorded signals yet. historical totals may predate this ledger.")
        for r in rows[(page - 1) * 5:page * 5]:
            lines += ["", "%s <b>$%s</b> · %s" % (DOT[r["verdict"]], esc(r["symbol"][:32]), r["verdict"]),
                      "scored %s · price %.6g" % (self.utc(r["t0"]), r["p0"])]
            if r["status"] == "resolved":
                lines.append("observed %s · price %.6g" % (self.utc(r.get("observed_at")), r["p1"]))
                lines.append("price %s · after fee %s" % (pct(r["ret"]), pct(r["net"])))
            elif r["status"] == "unavailable":
                lines.append("unavailable: no fresh price before the timeout; excluded from returns")
            else:
                lines.append("pending · target %s" % self.utc(r["due"]))
            token = r.get("token") or r["pair"]
            lines.append("<code>%s</code>" % esc(token[:64]))
        lines += ["", "last %d scored pools retained; totals include older records." % HISTORY_LIMIT,
                  "next: /history %s %d" % (verdict.lower(), page + 1) if page < pages else "end of retained history",
                  "<i>paper evaluation, not executed trades. not advice.</i>"]
        return "\n".join(lines)

    def status_text(self, f):
        last = self.field_ok_at.get(f.chain)
        age = "not yet" if last is None else "%ds ago" % max(0, time.time() - last)
        poll_age = "not yet" if self.last_poll_at is None else "%ds ago" % max(0, time.time() - self.last_poll_at)
        with f.lock:
            scored, pending = f.s.scored, len(f.s.shadows)
            feed_status = f.feed.status
        return ("<b>bot status</b> · %s\nmenu: %s\nlast successful field tick: %s\n"
                "last telegram poll: %s\n"
                "feed: %s\nscored %d · pending %d\nfield error: %s" % (
                    f.chain, "ready" if self.menu_ready else "retrying", age, poll_age, esc(str(feed_status)[:160]),
                    scored, pending, esc(self.field_errors.get(f.chain, "none"))))

    def me_text(self, u):
        a = self.account(u)
        st = a.stats()
        lines = ["<b>your paper account</b> · %s" % u["chain"], "equity $%.0f (%s) · %d trades · %d won" % (
            st["equity"], pct(st["equity"] / a.start - 1), st["trades"], st["wins"]), ""]
        for i, p in enumerate(a.open, 1):
            lines.append("%d. $%s $%.0f → %s" % (i, esc(p.symbol), p.size, pct(p.ret())))
        if not a.open:
            lines.append("no open positions. paste a CA and tap paper $50.")
        lines.append("\nexits: +100%, -35%, 30 min, or a rug. same rules as the bee.")
        return "\n".join(lines)

    def race_text(self, u, f):
        with f.lock:
            bee, rnd = f.s.accounts["bee"], f.s.accounts["random"]
            fw, g = f.s.forward(), f.s.gate()
        you = self.account(u, f.chain)
        lines = ["<b>the race on %s</b>" % f.chain]
        for name, a in (("🐝 the bee", bee), ("🎲 random", rnd), ("🫵 you", you)):
            lines.append("%s  $%.0f (%s)" % (name, a.equity, pct(a.equity / a.start - 1)))
        lines += ["", "<b>forward test</b>, +15 min, fees in"]
        for v in ("PASS", "WATCH", "SKIP"):
            x = fw[v]
            lines.append("%s %s %d pools · hit %s" % (DOT[v], v.lower(), x["n"], "%.0f%%" % (x["hit"] * 100) if x["n"] else "-"))
        lines += ["", "<b>graduation</b>: " + ("open" if g["open"] else "closed, paper only")]
        lines += ["%s %s: %s" % ("✅" if ok else "▫️", name, val) for name, ok, val in g["checks"]]
        return "\n".join(lines)

    def buy(self, chat, u, f, q, amt):
        s = self.find(f, q)
        if not s:
            return self.tg.send(chat, "no pool found for %s on %s." % (esc(q), f.chain))
        if s["liq"] <= 0:
            return self.tg.send(chat, "$%s has no pool liquidity yet. the paper account only trades real pools." % esc(s["symbol"]))
        a = self.account(u, f.chain)
        with f.lock:
            pos = a.buy(s, amt, now_ms(), None, "manual")
        if not pos:
            return self.tg.send(chat, "not enough paper cash. /me")
        return self.tg.send(chat, "bought $%s for $%.0f of paper at %.4g, after impact and fee.\n/me to watch it." % (
            esc(s["symbol"]), pos.size, pos.fill))

    def sell(self, chat, u, f, arg):
        a = self.account(u, f.chain)
        try:
            p = a.open[int(arg or "1") - 1]
        except (ValueError, IndexError):
            return self.tg.send(chat, "usage: /sell 1  (see /me)")
        with f.lock:
            c = a.close(p, now_ms(), "manual")
        return self.tg.send(chat, "sold $%s %s, %s$%.2f." % (esc(c["symbol"]), pct(c["ret"]), "+" if c["pnl"] >= 0 else "-", abs(c["pnl"])))

    def on_callback(self, q):
        data = q.get("data", "")
        chat = (q.get("message") or {}).get("chat", {}).get("id")
        if not chat:
            return
        u = self.user(q["from"], chat)
        if data.startswith("b:"):
            _, amt, pair = data.split(":", 2)
            self.tg.answer(q["id"], "paper order")
            return self.buy(chat, u, self.fields[u["chain"]], pair, self.parse_usd(amt))
        self.tg.answer(q["id"])

    # -------------------------------------------------------------- loop
    def broadcast(self, f, passes, closes):
        t = self.clock()
        for r in passes:
            text = ("🟢 <b>the bee passed $%s</b> · %s\n<code>%s</code>\nscore %.2f · mushroom %.2f · liq %s\n<i>paper brain. not advice.</i>"
                    % (esc(r["symbol"]), f.chain, esc(r.get("token", "")), r["comb"], r["vector"]["mushroom"]["value"], usd(r["liq"])))
            buttons = [[{"text": "paper $50", "callback_data": "b:50:" + r["pair"][:52]}]]
            if r.get("url", "").startswith("https://dexscreener.com/"):
                buttons[0].append({"text": "chart ↗", "url": r["url"]})
            with self.state_lock:
                targets = [u["chat"] for u in self.users.values() if u["alerts"] and u["chain"] == f.chain and u["chat"]]
            if self.channel:
                targets.append(self.channel)
            for chat in targets:
                if t - self.last_alert.get(chat, float("-inf")) < ALERT_GAP_S:
                    continue
                self.last_alert[chat] = t
                self.safe_send(chat, text, buttons)
        for u, c in closes:
            self.safe_send(u["chat"], "your paper $%s closed %s (%s), %s$%.2f." % (
                esc(c["symbol"]), pct(c["ret"]), c["reason"], "+" if c["pnl"] >= 0 else "-", abs(c["pnl"])))

    def safe_send(self, chat, text, buttons=None):
        try:
            self.tg.send(chat, text, buttons)
        except (TelegramError, OSError):
            pass

    def setup_menu(self, say=print):
        try:
            self.tg.call("setMyCommands", commands=COMMANDS)
            self.tg.call("setChatMenuButton", menu_button={"type": "commands"})
        except (TelegramError, OSError) as e:
            self.menu_ready = False
            say("menu setup failed (%s); commands still work, retrying" % type(e).__name__)
            return False
        self.menu_ready = True
        return True

    @staticmethod
    def retry_delay(error):
        return max(3, getattr(error, "retry_after", None) or 3)

    def run(self, say=print, stop=None):
        stop = stop or threading.Event()

        def fields():
            t_save = time.monotonic()
            while not stop.is_set():
                for f in self.fields.values():
                    try:
                        self.broadcast(f, *self.tick_field(f))
                        self.field_ok_at[f.chain] = time.time()
                        self.field_errors.pop(f.chain, None)
                    except Exception as e:
                        self.field_errors[f.chain] = type(e).__name__
                        say("field %s: %s" % (f.chain, type(e).__name__))
                if time.monotonic() - t_save > SAVE_EVERY_S:
                    t_save = time.monotonic()
                    try:
                        self.save()
                    except OSError as e:
                        say("state save failed: %s" % type(e).__name__)
                stop.wait(0.5)

        th = None
        try:
            while not stop.is_set():
                try:
                    me = self.tg.call("getMe")
                    break
                except (TelegramError, OSError) as e:
                    if isinstance(e, TelegramError) and e.fatal:
                        raise
                    say("telegram startup: %s, retrying" % type(e).__name__)
                    stop.wait(self.retry_delay(e))
            if stop.is_set():
                return
            say("beebrain bot @%s on %s. ctrl-c to stop." % (me.get("username"), ", ".join(self.fields)))
            self.setup_menu(say)
            menu_due = time.monotonic() + MENU_RETRY_S
            th = threading.Thread(target=fields, daemon=True)
            th.start()
            while not stop.is_set():
                if not self.menu_ready and time.monotonic() >= menu_due:
                    self.setup_menu(say)
                    menu_due = time.monotonic() + MENU_RETRY_S
                try:
                    updates = self.tg.updates(self.offset + 1 if self.offset else 0)
                    self.last_poll_at = time.time()
                    for upd in updates:
                        self.offset = max(self.offset, upd["update_id"])
                        try:
                            self.handle(upd)
                        except Exception as e:
                            say("reply failed: %s" % type(e).__name__)
                except (TelegramError, OSError) as e:
                    if isinstance(e, TelegramError) and e.fatal:
                        raise
                    say("telegram polling: %s, retrying" % type(e).__name__)
                    stop.wait(self.retry_delay(e))
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            if th is not None:
                th.join(timeout=45)
            if th is None or not th.is_alive():
                self.save()
            else:
                say("field worker still stopping; keeping the last saved state")


def check_telegram(tg):
    """read-only operator check; never consumes updates or changes telegram settings."""
    me = tg.call("getMe")
    commands = tg.call("getMyCommands") or []
    menu = tg.call("getChatMenuButton") or {}
    webhook = tg.call("getWebhookInfo") or {}
    names = {c["command"] for c in commands}
    missing = sorted({c["command"] for c in COMMANDS} - names)
    result = {"username": me.get("username"), "missing_commands": missing,
              "menu_type": menu.get("type"), "webhook_active": bool(webhook.get("url")),
              "pending_updates": webhook.get("pending_update_count", 0),
              "note": "api access only; does not prove the polling process is running"}
    result["ok"] = not missing and menu.get("type") == "commands" and not result["webhook_active"]
    return result


def read_token(path=None):
    tok = os.environ.get("BEEBRAIN_BOT_TOKEN", "").strip()
    if tok:
        return tok
    path = path or os.path.join(os.path.expanduser("~"), ".beebrain", "bot.token")
    with open(path) as fh:
        return fh.read().strip()


__all__ = ["BeeBot", "read_token", "CHAINS"]
