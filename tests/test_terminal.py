import io
import json
import os
import re

import pytest

from beebrain import cli
from beebrain.terminal import app

ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.join(HERE, "..", "examples", "trades_example.csv")


def plain_frame(monkeypatch, layout, post=1, cols=180, lines=52, **kw):
    monkeypatch.setenv("COLUMNS", str(cols))
    monkeypatch.setenv("LINES", str(lines))
    out = io.StringIO()
    rc = app.run(post=post, layout=layout, frames=50, plain=True, out=out, **kw)
    assert rc == 0
    rows = ANSI.sub("", out.getvalue()).rstrip("\n").split("\n")
    return rows


@pytest.mark.parametrize("layout,w,h", [("wide", 180, 52), ("compact", 84, 76)])
def test_plain_frame_has_exact_size(monkeypatch, layout, w, h):
    rows = plain_frame(monkeypatch, layout)
    assert len(rows) == h
    assert all(len(r) == w for r in rows)


@pytest.mark.parametrize("post", [2, 3])
@pytest.mark.parametrize("layout", ["wide", "compact"])
def test_later_stages_render(monkeypatch, post, layout):
    rows = plain_frame(monkeypatch, layout, post=post)
    assert len({len(r) for r in rows}) == 1


def test_labels_stay_honest(monkeypatch):
    text = "\n".join(plain_frame(monkeypatch, "wide"))
    assert "synthetic pools, sim account" in text
    assert "sim, fees in" in text
    assert "octopamine" in text
    assert "dopamine" not in text.replace("octopamine", "")


def test_trades_mode_says_sample_pools(monkeypatch):
    text = "\n".join(plain_frame(monkeypatch, "wide", trades=EXAMPLE))
    assert "LIVE ACCOUNT" in text and "your trades, sample pools" in text


def test_cli_sim_json(capsys):
    assert cli.main(["sim", "--seeds", "0-1", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [r["seed"] for r in rows] == [0, 1]
    assert {"final", "trades", "wins", "win_rate", "max_drawdown"} <= set(rows[0])


def test_cli_vector(capsys):
    assert cli.main(["sim", "--seeds", "5", "--vector", "30"]) == 0
    v = json.loads(capsys.readouterr().out)
    assert v["motor"]["verdict"] in ("PASS", "WATCH", "SKIP")
