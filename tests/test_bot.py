import json
import os

import pytest

from beebrain.bot.app import BeeBot, is_ca
from beebrain.bot.telegram import Telegram

from test_field import FIX, fixture_fetch

TOKENS = json.load(open(os.path.join(FIX, "ds_tokens_solana.json")))


class FakeApi:
    def __init__(self):
        self.sent = []

    def __call__(self, method, payload):
        self.sent.append((method, payload))
        if method == "getMe":
            return {"username": "beebrain_test_bot"}
        return {"message_id": len(self.sent)}

    def texts(self):
        return [p["text"] for m, p in self.sent if m == "sendMessage"]


@pytest.fixture
def bot(tmp_path):
    api = FakeApi()
    b = BeeBot(Telegram("123:abc", post=api), ["solana"], state_dir=str(tmp_path), fetch=fixture_fetch, clock=iter(range(0, 10 ** 6, 5)).__next__)
    return b, api


def msg(text, uid=7, chat=70):
    return {"update_id": 1, "message": {"text": text, "chat": {"id": chat}, "from": {"id": uid, "username": "tester"}}}


def fill(b):
    f = b.fields["solana"]
    for _ in range(60):
        b.tick_field(f)
    return f


def test_token_shape_is_checked():
    with pytest.raises(ValueError):
        Telegram("nope")


def test_ca_detection():
    assert is_ca("CkkNjyB6r1xraRyTrwejehZMSW8Bqw3123sV4aNXpump")
    assert is_ca("0x" + "ab" * 20)
    assert not is_ca("hello") and not is_ca("0x1234")


def test_start_and_scan(bot):
    b, api = bot
    b.handle(msg("/start"))
    assert "BeeBrain" in api.texts()[-1] and "not advice" in api.texts()[-1]
    fill(b)
    b.handle(msg("/scan", chat=71))
    assert "the bee on solana" in api.texts()[-1]


def test_paste_a_ca_scores_without_side_effects(bot):
    b, api = bot
    f = fill(b)
    ca = TOKENS[0]["baseToken"]["address"]
    before = (f.s.scored, len(f.s.shadows), f.s.rng.state(), list(f.s.brain.w))
    b.handle(msg(ca, chat=72))
    text = api.texts()[-1]
    assert ca in text and any(v in text for v in ("PASS", "WATCH", "SKIP"))
    assert (f.s.scored, len(f.s.shadows), f.s.rng.state(), list(f.s.brain.w)) == before


def test_paper_buy_sell_and_persist(bot, tmp_path):
    b, api = bot
    fill(b)
    pool = next(p for p in TOKENS if float((p.get("liquidity") or {}).get("usd") or 0) > 5000)
    b.handle(msg("/buy %s 50" % pool["baseToken"]["address"], chat=73))
    assert "bought" in api.texts()[-1]
    a = b.users["7"]["acct"]["solana"]
    assert len(a.open) == 1 and a.cash == pytest.approx(450)
    b.save()
    again = BeeBot(Telegram("123:abc", post=FakeApi()), ["solana"], state_dir=str(tmp_path), fetch=fixture_fetch)
    assert len(again.users["7"]["acct"]["solana"].open) == 1
    b.handle(msg("/sell 1", chat=74))
    assert "sold" in api.texts()[-1] and not a.open


def test_buy_button_callback(bot):
    b, api = bot
    fill(b)
    pool = next(p for p in TOKENS if float((p.get("liquidity") or {}).get("usd") or 0) > 5000)
    b.handle({"update_id": 2, "callback_query": {"id": "q1", "data": "b:25:" + pool["pairAddress"],
                                                 "from": {"id": 8}, "message": {"chat": {"id": 80}}}})
    assert any(m == "answerCallbackQuery" for m, _ in api.sent)
    assert "bought" in api.texts()[-1]


def test_alerts_go_to_subscribers_and_escape_html(bot):
    b, api = bot
    b.handle(msg("/alerts on", chat=90, uid=9))
    f = b.fields["solana"]
    r = {"symbol": "<b>evil</b>", "token": "T", "pair": "P" * 44, "comb": 0.7, "liq": 30000.0, "url": "https://dexscreener.com/solana/x",
         "vector": {"mushroom": {"value": 0.6}}}
    b.broadcast(f, [r], [])
    last = api.texts()[-1]
    assert "&lt;b&gt;evil&lt;/b&gt;" in last and "<b>evil</b>" not in last


def test_race_and_me(bot):
    b, api = bot
    fill(b)
    b.handle(msg("/race", chat=75))
    assert "the race on solana" in api.texts()[-1] and "graduation" in api.texts()[-1]
    b.handle(msg("/me", chat=76))
    assert "your paper account" in api.texts()[-1]
