import json
import os
import shutil
import subprocess

import pytest

from beebrain import brain
from beebrain.field import paper
from beebrain.field.features import features, norm_dexscreener, reflex
from beebrain.field.rng import FieldRng
from beebrain.field.session import FieldSession

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
BEE_JS = os.path.join(HERE, "..", "web", "trade", "bee.js")
NOW = 1790424000000.0


def pairs():
    return [norm_dexscreener(p) for p in json.load(open(os.path.join(FIX, "ds_tokens_solana.json")))]


def snap(**kw):
    s = {"chain": "solana", "pair": "P1", "token": "T1", "symbol": "BEE", "name": "bee", "dex": "raydium", "url": "",
         "price": 1.0, "liq": 50000.0, "fdv": 500000.0, "created_ms": NOW - 3600e3, "buys_m5": 30, "sells_m5": 10,
         "buys_h1": 300, "sells_h1": 200, "vol_m5": 5000.0, "vol_h1": 40000.0, "chg_m5": 5.0, "chg_h1": 20.0,
         "src": "test", "t_ms": NOW}
    s.update(kw)
    return s


def test_rng_is_deterministic_and_uniform():
    a, b = FieldRng(5), FieldRng(5)
    xs = [a.random() for _ in range(2000)]
    assert xs == [b.random() for _ in range(2000)]
    assert all(0 <= x < 1 for x in xs) and 0.45 < sum(xs) / len(xs) < 0.55


def test_field_brain_keeps_the_sparse_code():
    s = FieldSession()
    for p in pairs():
        obs, noise, _ = features(p, [x["vol_h1"] for x in pairs()], NOW)
        assert len(s.brain.code(obs)) == brain.KC_ACTIVE


@pytest.mark.parametrize("kw,reason", [
    ({"liq": 0.0}, "no pool liquidity yet, bonding curve"), ({"liq": 1500.0}, "thin liquidity"),
    ({"fdv": 50e6}, "fdv far above liquidity"), ({"buys_h1": 40, "sells_h1": 0}, "no sells, possible honeypot"),
    ({"chg_m5": -60.0}, "dumping now"), ({"chg_h1": -85.0}, "rugged in the last hour")])
def test_reflexes_trip_and_force_skip(kw, reason):
    s = snap(**kw)
    assert reason in reflex(s)
    sess = FieldSession()
    sess.ingest([s], NOW)
    assert sess.score_next(NOW)["verdict"] == "SKIP"


def test_clean_pool_passes_the_reflexes():
    assert reflex(snap()) == []


def test_paper_fill_fee_and_impact():
    a = paper.Account("t")
    pos = a.buy(snap(price=2.0, liq=100000.0), 100.0, NOW)
    assert a.cash == pytest.approx(400.0)
    assert pos.fill == pytest.approx(2.0 * (1 + 2 * 100 / 100000))
    # flat price: you lose the fee both ways and the impact both ways, never more
    assert -0.03 < pos.ret() < -0.02
    a.mark({"P1": snap(price=5.0, liq=100000.0)}, NOW + 60e3)     # x2.5 clears +100% after fees
    assert a.closed and a.closed[-1]["reason"] == "take profit"
    assert a.equity == pytest.approx(a.cash)


@pytest.mark.parametrize("px,liq,why", [(0.5, 100000.0, "stop loss"), (1.0, 10000.0, "rug"), (0.05, 100000.0, "rug")])
def test_paper_exits(px, liq, why):
    a = paper.Account("t")
    a.buy(snap(price=1.0, liq=100000.0), 50.0, NOW)
    a.mark({"P1": snap(price=px, liq=liq)}, NOW + 60e3)
    assert a.closed[-1]["reason"] == why


def test_max_hold_exit():
    a = paper.Account("t")
    a.buy(snap(), 50.0, NOW)
    a.mark({"P1": snap()}, NOW + 31 * 60e3)
    assert a.closed[-1]["reason"] == "max hold"


def test_forward_test_resolves_after_the_horizon_and_teaches_skips():
    s = FieldSession()
    s.ingest([snap(chg_m5=-70.0)], NOW)          # reflex, so a SKIP the bee does not take
    s.score_next(NOW)
    assert len(s.shadows) == 1
    w0 = list(s.brain.w)
    s.ingest([snap(chg_m5=-70.0, price=2.0, t_ms=NOW + 10 * 60e3)], NOW + 10 * 60e3)
    s.mark(NOW + 10 * 60e3)
    assert len(s.shadows) == 1                    # not due yet
    s.ingest([snap(price=2.0, t_ms=NOW + 16 * 60e3)], NOW + 16 * 60e3)
    s.mark(NOW + 16 * 60e3)
    f = s.forward()["SKIP"]
    assert f["n"] == 1 and f["hit"] == 1.0 and f["avg_net"] == pytest.approx(2 * 0.98 - 1)
    assert s.brain.w != w0 and s.brain.sugar == 1


def test_bee_trade_close_broadcasts_to_the_brain():
    s = FieldSession()
    s.ingest([snap()], NOW)
    r = s.score_next(NOW)
    if not r["took"]:
        pytest.skip("this wiring does not take the test pool")
    s.ingest([snap(price=3.0, t_ms=NOW + 60e3)], NOW + 60e3)
    s.mark(NOW + 60e3)
    assert s.brain.sugar + s.brain.pain >= 1 and s.brain.resolved == 1


def test_session_survives_a_round_trip():
    s = FieldSession()
    s.ingest(pairs(), NOW)
    while s.score_next(NOW):
        pass
    s.mark(NOW + 60e3)
    d = json.loads(json.dumps(s.to_json()))
    s2 = FieldSession.from_json(d)
    assert s2.brain.w == s.brain.w and s2.rng.state() == s.rng.state()
    assert s2.accounts["bee"].equity == pytest.approx(s.accounts["bee"].equity)
    assert s2.forward() == s.forward()


def test_gate_starts_closed():
    g = FieldSession().gate()
    assert g["open"] is False and len(g["checks"]) == 3


# ------------------------------------------------------ browser twin parity ---
NODE = shutil.which("node")

JS = r"""
const Bee = require(process.argv[2]);
const raw = require(process.argv[3]);
const now = Number(process.argv[4]);
const r = new Bee.FieldRng(5);
const rng = Array.from({length: 50}, () => r.random());
const s = new Bee.FieldSession("solana");
const snaps = raw.map(Bee.normDexscreener);
s.ingest(snaps, now);
const out = [];
let x;
while ((x = s.scoreNext(now))) out.push({pair: x.pair, obs: x.obs, noise: x.noise, reasons: x.reasons,
  act: x.act, verdict: x.verdict, comb: x.comb, took: x.took});
const b = new Bee.BeeBrain(new Bee.FieldRng(5));
console.log(JSON.stringify({rng, kc: b.kcIn.slice(0, 20), tie: b.tie.slice(0, 5), out,
  bee: s.accounts.bee.equity, random: s.accounts.random.open.length, consts: Bee.C}));
"""


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_browser_twin_matches_python(tmp_path):
    script = tmp_path / "twin.js"
    script.write_text(JS)
    res = subprocess.run([NODE, str(script), os.path.abspath(BEE_JS), os.path.join(FIX, "ds_tokens_solana.json"), repr(NOW)],
                         capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    r = FieldRng(5)
    assert js["rng"] == [r.random() for _ in range(50)]
    b = brain.BeeBrain(FieldRng(5))
    assert js["kc"] == b.kc_in[:20] and js["tie"] == b.tie[:5]
    s = FieldSession("solana")
    s.ingest(pairs(), NOW)
    py = []
    while True:
        x = s.score_next(NOW)
        if not x:
            break
        py.append(x)
    assert len(py) == len(js["out"]) > 5
    for a, j in zip(py, js["out"]):
        assert a["pair"] == j["pair"] and a["reasons"] == j["reasons"] and a["verdict"] == j["verdict"]
        assert a["act"] == j["act"] and a["took"] == j["took"]
        assert a["comb"] == pytest.approx(j["comb"], abs=1e-9) and a["noise"] == pytest.approx(j["noise"], abs=1e-12)
        for k, v in a["obs"].items():
            assert v == pytest.approx(j["obs"][k], abs=1e-12)
    assert js["bee"] == pytest.approx(s.accounts["bee"].equity)
    # the constants the browser uses are the ones the python brain uses
    for k, v in js["consts"].items():
        if hasattr(brain, k):
            assert getattr(brain, k) == v, k


def fixture_fetch(url):
    from beebrain.field.feed import RateLimited
    if "geckoterminal" in url:
        raise RateLimited(url)
    if "token-profiles" in url:
        return json.load(open(os.path.join(FIX, "ds_profiles.json")))
    if "token-boosts" in url:  # latest and top
        return []
    if "/tokens/v1/" in url:
        return json.load(open(os.path.join(FIX, "ds_tokens_solana.json")))
    if "/latest/dex/pairs/" in url:
        return {"pairs": json.load(open(os.path.join(FIX, "ds_tokens_solana.json")))}
    raise AssertionError(url)


@pytest.mark.parametrize("layout,w,h", [("wide", 180, 52), ("compact", 84, 96)])
def test_trade_terminal_renders_offline(monkeypatch, layout, w, h):
    import io
    import re
    from beebrain.terminal import field as tf
    monkeypatch.setenv("COLUMNS", "180")
    monkeypatch.setenv("LINES", "52")
    out = io.StringIO()
    assert tf.run(layout=layout, plain=True, frames=80, out=out, fetch=fixture_fetch, save=False) == 0
    rows = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", out.getvalue()).rstrip("\n").split("\n")
    assert len(rows) == h and all(len(r) == w for r in rows)
    text = "\n".join(rows)
    assert "paper" in text and "THE RACE" in text and "FORWARD TEST" in text


def test_feed_backs_off_gecko_on_429():
    from beebrain.field.feed import GT_DISCOVER_S, Feed
    f = Feed("solana", fetch=fixture_fetch)
    new, _ = f.poll(0.0, [])
    assert new and f.status == "live" and f.gt_wait == 2 * GT_DISCOVER_S


def test_report_from_a_session():
    from beebrain.field.report import report, snapshot, spearman

    class F:
        calls, errors, status = 3, 0, "live"
    s = FieldSession()
    for i in range(12):
        s.ingest([snap(pair="P%d" % i, symbol="B%d" % i, buys_h1=50 + 40 * i, chg_m5=-70.0 if i % 4 == 0 else 3.0)], NOW)
        s.score_next(NOW)
    for i in range(12):
        s.ingest([snap(pair="P%d" % i, price=1.0 + 0.05 * i, t_ms=NOW + 16 * 60e3)], NOW + 16 * 60e3)
    s.mark(NOW + 16 * 60e3)
    d = json.loads(json.dumps(snapshot(s, NOW, F())))
    md = report(d)
    assert "## forward test" in md and "killed by a reflex" in md and "bee score" in md
    assert len(d["log"]) == 12
    assert spearman([1, 2, 3, 4, 5, 6, 7, 8], [2, 4, 6, 8, 10, 12, 14, 16]) == pytest.approx(1.0)
