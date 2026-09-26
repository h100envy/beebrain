import random

import pytest

from beebrain import brain
from beebrain.brain import KC_ACTIVE, N_KC, BeeBrain, BeeBrain9
from beebrain.engine import Engine, run
from beebrain.market import Pool


def pools(n=200, seed=1):
    rng = random.Random(seed)
    return [Pool(rng, i, rng.random(), rng.uniform(-0.1, 0.1)) for i in range(n)]


def test_same_seed_same_event_log():
    a, b = run(7, days=3), run(7, days=3)
    assert a.events and a.event_hash() == b.event_hash()
    assert a.summary() == b.summary()


def test_different_seed_different_event_log():
    assert run(7, days=3).event_hash() != run(8, days=3).event_hash()


def test_sparse_code_fires_exactly_kc_active():
    b = BeeBrain(random.Random(3))
    for p in pools():
        act = b.code(p.obs)
        assert len(act) == KC_ACTIVE
        assert all(0 <= k < N_KC for k in act)


def test_ninth_glomerulus_keeps_the_on_chain_code_at_kc_active():
    b = BeeBrain9(random.Random(3))
    for p in pools(50):
        p.obs["tg velocity"] = 0.9
        act = b.code(p.obs)
        assert len([k for k in act if k < N_KC]) == KC_ACTIVE


@pytest.mark.parametrize("won", [True, False])
def test_learning_only_touches_cells_that_fired(won):
    b = BeeBrain(random.Random(4))
    b.w = [random.Random(k).uniform(0.2, 0.8) for k in range(N_KC)]
    act = b.code(pools(1)[0].obs)
    before = list(b.w)
    b.after_trade(act, won)
    changed = {k for k in range(N_KC) if b.w[k] != before[k]}
    assert changed == set(act)
    for k in act:
        assert (b.w[k] > before[k]) if won else (b.w[k] < before[k])


def test_skipped_pool_learning_stays_on_its_own_cells():
    e = Engine(11)
    for _ in range(60):
        e.next_pool()
        e.tick_positions()
        before = list(e.brain.w)
        t = e.thought
        closing = [p for p in e.open if p.age >= p.life]
        e.act()
        if not t["take"] and not closing:
            changed = {k for k in range(N_KC) if e.brain.w[k] != before[k]}
            assert changed <= set(t["act"])


def test_reward_and_punishment_are_separate_channels():
    b = BeeBrain(random.Random(5))
    act = b.code(pools(1)[0].obs)
    b.after_trade(act, True)
    b.after_trade(act, False)
    assert (b.sugar, b.pain) == (1, 1)


def fade_steps(first, then):
    """train some cells with `first`, count `then` events until they are back past neutral"""
    b = BeeBrain(random.Random(6))
    act = b.code(pools(1)[0].obs)
    for _ in range(12):
        b.after_trade(act, first)
    k = next(iter(act))
    n = 0
    while (b.w[k] > 0.5) == first and n < 1000:
        b.after_trade(act, then)
        n += 1
    return n


def test_punishment_memory_does_not_fade_faster_than_reward():
    assert brain.PUNISH_LR >= brain.OCTOPAMINE_LR
    rug_fade = fade_steps(first=False, then=True)      # sugar needed to erase a rug memory
    print_fade = fade_steps(first=True, then=False)    # punishment needed to erase a print memory
    assert rug_fade >= print_fade


def test_bundled_pools_always_skip():
    b = BeeBrain(random.Random(8))
    b.w = [1.0] * N_KC                  # even a brain that loves everything
    for p in pools(300):
        p.obs["bundle"] = 1.0
        assert b.think(p, None)["verdict"] == "SKIP"


def test_bundled_pools_skip_in_a_full_run():
    e = Engine(2)
    seen = 0
    for _ in range(9 * 40):
        e.step()
        if e.pool.obs["bundle"] > 0.5:
            seen += 1
            assert e.thought["verdict"] == "SKIP" and not e.thought["take"]
    assert seen > 20


def test_waggle_vector_has_one_value_per_lobe():
    e = Engine(5)
    for _ in range(50):
        e.step()
    v = brain.waggle_vector(e.pool, e.thought)
    assert set(v) >= {"pool", "mushroom", "antennal", "optic", "central", "motor", "consensus"}
    assert v["motor"]["verdict"] in ("PASS", "WATCH", "SKIP")
    assert v["kenyon_active"] == KC_ACTIVE
