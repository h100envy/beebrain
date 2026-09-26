import os

import pytest

from beebrain.engine import FEE, Engine, Position, parse_seeds, run
from beebrain.live import Live, read_trades

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "..", "examples", "trades_example.csv")

# the ten seed table in docs/article.md: seed -> (final, trades, wins)
ARTICLE = {6: (6966, 49, 33), 8: (6661, 43, 28), 4: (2942, 41, 24), 7: (1998, 39, 24), 1: (1695, 30, 20),
           5: (1526, 40, 22), 9: (1049, 27, 15), 3: (754, 22, 8), 0: (589, 19, 8), 2: (486, 25, 11)}


@pytest.mark.parametrize("seed", sorted(ARTICLE))
def test_sim_reproduces_the_article_table(seed):
    s = run(seed, 9, record=False).summary()
    assert (round(s["final"]), s["trades"], s["wins"]) == ARTICLE[seed]


def test_fee_charged_once_per_round_trip():
    e = Engine(1)
    e.next_pool()
    cash0 = e.cash
    pos = Position(e.rng, e.pool, 100.0, e.thought["act"], False, e.n)
    e.cash -= pos.size
    e.open.append(pos)
    assert e.cash == pytest.approx(cash0 - 100.0)          # no fee on the way in
    while e.open:
        e.tick_positions()
    assert e.cash == pytest.approx(cash0 - 100.0 + 100.0 * (1 + pos.final) * (1 - FEE))
    name, pnl, final, _, _ = e.closed[-1]
    assert pnl == pytest.approx(100.0 * ((1 + final) * (1 - FEE) - 1))


def test_equity_is_cash_plus_marked_positions():
    e = Engine(6)
    checked = 0
    for _ in range(200):
        e.step()
        marked = sum(p.size * (1 + p.path[min(p.age, p.life)]) for p in e.open)
        assert e.equity == pytest.approx(e.cash + marked)
        checked += bool(e.open)
    assert checked > 20


def test_parse_seeds():
    assert parse_seeds("0-3") == [0, 1, 2, 3]
    assert parse_seeds("1,4,7") == [1, 4, 7]
    assert parse_seeds("2, 5-6") == [2, 5, 6]


def test_trades_csv_skips_the_header():
    rows = read_trades(EXAMPLE)
    assert [r[1] for r in rows] == ["$EXAMPLE", "$SAMPLE", "$DEMO"]
    assert rows[0] == (1.0, "$EXAMPLE", 50.0, 62.0)


def test_live_account_plays_back_by_day():
    L = Live(EXAMPLE, 500.0)
    L.log = []
    L.advance(0)                       # day 1
    assert len(L.done) == 1 and L.equity == pytest.approx(500 + 50 * 0.62)
    L.advance(40 * 5)                  # day 6, everything in
    assert len(L.done) == 3
    assert L.equity == pytest.approx(500 + 31 - 17.5 + 84)
    assert L.max_dd < 0
    assert all(tone in ("good", "bad") for _, _, tone in L.log)
