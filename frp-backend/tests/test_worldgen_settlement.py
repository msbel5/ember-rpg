from engine.worldgen import generate_settlement_layout, generate_world, seed_civilizations, seed_species, simulate_history


def _settlement_world(seed: int = 42):
    return simulate_history(seed_civilizations(seed_species(generate_world(seed, "standard"))))


def test_settlement_layout_has_organic_roads_buildings_and_furniture():
    world = _settlement_world()
    region_id = world.settlements[0].region_id
    layout = generate_settlement_layout(world, region_id)

    assert (layout.width, layout.height) == (80, 60)
    assert len(layout.buildings) >= 13
    assert len(layout.furniture) >= 20
    assert layout.center_feature["kind"] in {"well", "fountain"}
    assert any(building["kind"] == "town_hall" for building in layout.buildings)
    assert len({building["kind"] for building in layout.buildings}) >= 10
    assert len({x for x, _ in layout.road_tiles}) >= 20
    assert len({y for _, y in layout.road_tiles}) >= 15
    for building in layout.buildings:
        assert building["doors"]
        for door in building["doors"]:
            assert tuple(door["adjacent"][0]) in set(layout.road_tiles)

