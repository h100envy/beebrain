"""
the beebrain telegram bot. the same field as /trade and `beebrain trade`: the bee scores
live pools, and every user gets a paper account of their own.

  beebrain bot --token-file ~/.beebrain/bot.token --chains solana,base [--channel @yourchannel]

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
from ..field.session import FieldSession
from .telegram import TelegramError

SCORE_EVERY_S = 1.5
MARK_EVERY_S = 3.0
SAVE_EVERY_S = 60.0
ALERT_GAP_S = 15.0
CMD_GAP_S = 0.8
MAX_BUY = 500.0
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
            return FieldSession(self.chain)

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
        with f.lock:
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

    def run(self, say=print):
        stop = threading.Event()

        def fields():
            t_save = time.time()
            while not stop.is_set():
                for f in self.fields.values():
                    try:
                        self.broadcast(f, *self.tick_field(f))
                    except Exception as e:          # a bad tick must not kill the bot
                        say("field %s: %s" % (f.chain, e))
                if time.time() - t_save > SAVE_EVERY_S:
                    t_save = time.time()
                    self.save()
                stop.wait(0.5)

        th = threading.Thread(target=fields, daemon=True)
        th.start()
        me = self.tg.call("getMe")
        say("beebrain bot @%s on %s. ctrl-c to stop." % (me.get("username"), ", ".join(self.fields)))
        self.tg.call("setMyCommands", commands=[
            {"command": "scan", "description": "the best pools the bee scored"},
            {"command": "race", "description": "you vs the bee vs random, and the forward test"},
            {"command": "me", "description": "your paper account"},
            {"command": "alerts", "description": "on or off: a message for every PASS"},
            {"command": "chain", "description": "switch chain"},
            {"command": "help", "description": "what this is"}])
        try:
            while True:
                try:
                    for upd in self.tg.updates(self.offset + 1 if self.offset else 0):
                        self.offset = max(self.offset, upd["update_id"])
                        try:
                            self.handle(upd)
                        except (TelegramError, OSError) as e:
                            say("reply failed: %s" % e)
                except (TelegramError, OSError) as e:
                    say("telegram: %s, retrying" % e)
                    time.sleep(3)
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            self.save()


def read_token(path=None):
    tok = os.environ.get("BEEBRAIN_BOT_TOKEN", "").strip()
    if tok:
        return tok
    path = path or os.path.join(os.path.expanduser("~"), ".beebrain", "bot.token")
    with open(path) as fh:
        return fh.read().strip()


__all__ = ["BeeBot", "read_token", "CHAINS"]
