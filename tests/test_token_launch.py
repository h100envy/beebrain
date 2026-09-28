"""a single verified-format address flows unchanged to every launch surface."""
import importlib.util
from pathlib import Path

import pytest

# The launch helper is repository tooling, not part of the installed package.
spec = importlib.util.spec_from_file_location("token_launch", Path(__file__).resolve().parents[1] / "brand/token_launch.py")
launch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launch)
overlay_text = launch.overlay_text
token_html = launch.token_html
token_markdown = launch.token_markdown
validate = launch.validate


def test_empty_address_is_explicit_and_cannot_be_copied():
    config = {"ticker": "BEEBRAIN", "chain": "", "contract": ""}
    assert ' disabled' in token_html(config)
    assert "not announced" in token_html(config) and "not announced" in token_markdown(config)
    assert overlay_text(config) == "$BEEBRAIN   CA: "


@pytest.mark.parametrize("chain,ca", [("solana", "A" * 44), ("base", "0x" + "ab" * 20)])
def test_full_address_is_identical_across_surfaces(chain, ca):
    config = {"ticker": "BEEBRAIN", "chain": chain, "contract": ca}
    assert ca in token_html(config) and ca in token_markdown(config) and ca in overlay_text(config)
    assert ' disabled' not in token_html(config)


@pytest.mark.parametrize("update", [
    {"ticker": "<script>"}, {"contract": "hello", "chain": "solana"},
    {"contract": "A" * 44}, {"contract": "0x" + "ab" * 20, "chain": "solana"},
    {"contract": "A" * 44, "chain": "base"}, {"chain": "unknown"},
    {"contract": "A" * 44 + "\n", "chain": "solana"},
])
def test_invalid_configuration_is_rejected(update):
    config = {"ticker": "BEEBRAIN", "chain": "", "contract": ""}
    config.update(update)
    with pytest.raises(ValueError):
        validate(config)
