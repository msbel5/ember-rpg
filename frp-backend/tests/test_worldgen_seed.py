from engine.worldgen import WorldSeed
from engine.worldgen.world_seed import stable_seed_from_parts


def test_world_seed_is_stable_for_text_and_numbers():
    assert int(WorldSeed(42)) == 42
    assert int(WorldSeed("42")) == 42
    assert int(WorldSeed("ember-demo")) == int(WorldSeed("ember-demo"))
    assert stable_seed_from_parts("ember", "demo", 1) == stable_seed_from_parts("ember", "demo", 1)


def test_world_seed_derives_distinct_named_subseeds():
    seed = WorldSeed("ember-demo")
    derived = {
        seed.terrain_seed(),
        seed.settlement_seed(),
        seed.npc_seed(),
        seed.quest_seed(),
        seed.economy_seed(),
        seed.weather_seed(),
        seed.history_seed(),
    }
    assert len(derived) == 7

