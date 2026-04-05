from __future__ import annotations

import engine.api.gameplay_bridge as gameplay_bridge

from engine.api.campaign.runtime import CampaignRuntime
from engine.api.campaign.party_bridge import maybe_handle_party_command
from engine.api.campaign.state_sync import sync_context_clock
from engine.kernel.gameplay import spawn_ground_item_entity
from engine.kernel.game_state import FORMATIONS
from engine.kernel.progression import ProgressionState
from engine.world.entity import Entity, EntityType


def _make_campaign() -> tuple[CampaignRuntime, object]:
    runtime = CampaignRuntime()
    context = runtime.create_campaign(player_name="RuntimeTester", seed=77)
    return runtime, context


def _inject_companion(
    context,
    *,
    base_id: str,
    name: str,
    role: str,
    hostile: bool = False,
):
    from engine.kernel.actor_records import create_monster_actor

    companion = create_monster_actor(
        {
            "id": base_id,
            "name": name,
            "type": "monster",
            "hp": 12,
            "armor_class": 10,
            "stats": {"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10},
        },
        faction_id="raiders" if hostile else "allies",
    )
    companion.identity.actor_type = "npc"
    companion.raw_payload["role"] = role
    companion.raw_payload["hostile"] = hostile
    context.kernel_runtime["actors"][companion.identity.actor_id] = companion
    return companion


def _add_workstation(context, *, workstation_id: str, name: str, offset: tuple[int, int] = (1, 0)) -> None:
    x = int(context.position[0]) + int(offset[0])
    y = int(context.position[1]) + int(offset[1])
    entity = Entity(
        id=workstation_id,
        entity_type=EntityType.FURNITURE,
        name=name,
        position=(x, y),
        glyph="#",
        color="orange",
        blocking=False,
        hp=1,
        max_hp=1,
        disposition="neutral",
        job=name.lower().replace(" ", "_"),
    )
    context.spatial_index.add(entity)
    context.entities[workstation_id] = {
        "name": name,
        "type": "furniture",
        "position": [x, y],
        "role": name.lower().replace(" ", "_"),
        "template": name.lower().replace(" ", "_"),
        "context_actions": ["examine", "use"],
        "entity_ref": entity,
    }


def _first_scheduled_npc(context):
    for entity_id, record in context.entities.items():
        if entity_id == "player" or not isinstance(record, dict):
            continue
        entity_ref = record.get("entity_ref")
        schedule = getattr(entity_ref, "schedule", None)
        entries = getattr(schedule, "entries", None)
        if entries is None and isinstance(schedule, dict):
            entries = schedule.get("entries")
        if entries:
            return entity_id, record
    raise AssertionError("Expected at least one scheduled NPC in the region")


def _set_npc_schedule(context, entity_id: str, entries: list[dict]) -> None:
    record = context.entities[entity_id]
    entity_ref = record.get("entity_ref")
    if entity_ref is None:
        raise AssertionError("Expected projected entity_ref for scheduled NPC")
    payload = {"npc_id": entity_id, "npc_name": record.get("name", entity_id), "entries": entries}
    entity_ref.schedule = payload
    record["schedule"] = payload


def _set_progression_state(
    context,
    *,
    skill_points: int = 0,
    proficiency_points: int = 0,
    ability_increases: int = 0,
) -> None:
    player = context.kernel_runtime["actors"]["player"]
    class_id = str(player.raw_payload.get("class_name", "warrior")).lower()
    progression = ProgressionState(
        actor_id="player",
        xp=int(player.raw_payload.get("xp", 0)),
        level=int(player.raw_payload.get("level", 1)),
        classes=[class_id],
        class_levels={class_id: int(player.raw_payload.get("level", 1))},
        bab=int(player.raw_payload.get("bab", 0)),
        saves={str(key): int(value) for key, value in dict(player.raw_payload.get("saves", {})).items()},
        proficiency_points_available=proficiency_points,
        skill_points_available=skill_points,
        ability_increases_available=ability_increases,
    )
    player.raw_payload["progression"] = progression.to_dict()


def _schedule_entries(record: dict) -> list[dict]:
    entity_ref = record.get("entity_ref")
    schedule = getattr(entity_ref, "schedule", None)
    if isinstance(schedule, dict):
        return [dict(item) for item in schedule.get("entries", []) if isinstance(item, dict)]
    entries = getattr(schedule, "entries", None) or []
    normalized = []
    for item in entries:
        if hasattr(item, "to_dict"):
            normalized.append(item.to_dict())
        elif isinstance(item, dict):
            normalized.append(dict(item))
    return normalized


def _expected_schedule_entry(entries: list[dict], hour: int) -> dict:
    ordered = sorted(entries, key=lambda item: int(item.get("hour", 0)))
    eligible = [item for item in ordered if int(item.get("hour", 0)) <= int(hour) % 24]
    return dict(eligible[-1] if eligible else ordered[-1])


def test_run_command_pickup_uses_ground_item_authority() -> None:
    runtime, context = _make_campaign()
    spawn_ground_item_entity(
        context,
        item={"id": "iron_ore", "name": "Iron Ore", "qty": 1},
    )

    result = runtime.run_command(context.campaign_id, "pickup iron ore")

    assert result["command_type"] == "inventory"
    assert "picked up" in result["narrative"].lower()
    assert context.find_inventory_item("iron_ore") is not None
    assert any(item.get("id") == "iron_ore" for item in result["campaign"]["player"]["inventory"])
    assert context.campaign_state.get("ground_items", []) == []


def test_run_command_drop_persists_ground_item_authority_for_next_command() -> None:
    runtime, context = _make_campaign()
    context.add_item({"id": "iron_ore", "name": "Iron Ore", "qty": 1}, merge=True)

    drop_result = runtime.run_command(context.campaign_id, "drop iron ore")

    assert drop_result["command_type"] == "inventory"
    assert "dropped" in drop_result["narrative"].lower()
    assert len(context.campaign_state.get("ground_items", [])) == 1

    pickup_result = runtime.run_command(context.campaign_id, "pickup iron ore")

    assert pickup_result["command_type"] == "inventory"
    assert "picked up" in pickup_result["narrative"].lower()
    assert context.find_inventory_item("iron_ore") is not None


def test_run_command_spell_uses_kernel_spell_flow() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.spell_points = 10
    player.raw_payload["max_spell_points"] = 10

    result = runtime.run_command(context.campaign_id, "cast magic missile")

    assert result["command_type"] == "spell"
    assert "magic missile" in result["narrative"].lower()
    assert player.spell_points == 8
    assert int(player.raw_payload.get("last_cast_tick", -1)) >= 0


def test_run_command_repeated_pickup_then_missing() -> None:
    runtime, context = _make_campaign()
    spawn_ground_item_entity(context, item={"id": "iron_ore", "name": "Iron Ore", "qty": 1}, entity_id="ore_a")
    spawn_ground_item_entity(context, item={"id": "iron_ore", "name": "Iron Ore", "qty": 1}, entity_id="ore_b")

    first = runtime.run_command(context.campaign_id, "pickup iron ore")
    second = runtime.run_command(context.campaign_id, "pickup iron ore")
    third = runtime.run_command(context.campaign_id, "pickup iron ore")

    assert first["command_type"] == "inventory"
    assert second["command_type"] == "inventory"
    assert "nothing to pick up" in third["narrative"].lower()
    stack = context.find_inventory_item("iron_ore")
    assert stack is not None
    assert int(stack.get("qty", 1)) == 2
    assert context.campaign_state.get("ground_items", []) == []


def test_run_command_repeated_drop_then_missing() -> None:
    runtime, context = _make_campaign()
    context.add_item({"id": "iron_ore", "name": "Iron Ore", "qty": 2}, merge=True)

    first = runtime.run_command(context.campaign_id, "drop iron ore")
    second = runtime.run_command(context.campaign_id, "drop iron ore")
    third = runtime.run_command(context.campaign_id, "drop iron ore")

    assert first["command_type"] == "inventory"
    assert second["command_type"] == "inventory"
    assert "don't have" in third["narrative"].lower()
    assert len(context.campaign_state.get("ground_items", [])) == 2


def test_run_command_craft_repeated_missing_ingredients_stays_non_mutating() -> None:
    runtime, context = _make_campaign()
    context.kernel_runtime["actors"]["player"].skills["smithing"] = 15
    _add_workstation(context, workstation_id="test_forge_missing_ingredients", name="Practice Forge")
    baseline_inventory = list(context.player.inventory)

    first = runtime.run_command(context.campaign_id, "craft iron bar")
    _add_workstation(context, workstation_id="test_forge_missing_ingredients_retry", name="Practice Forge")
    second = runtime.run_command(context.campaign_id, "craft iron bar")

    assert first["command_type"] == "craft"
    assert second["command_type"] == "craft"
    assert "missing ingredient" in first["narrative"].lower()
    assert "missing ingredient" in second["narrative"].lower()
    assert context.player.inventory == baseline_inventory


def test_run_command_craft_requires_nearby_workstation_without_mutation() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.skills["smithing"] = 15
    player.xp = 0
    context.position = [0, 0]
    context.player_entity.position = (0, 0)
    context.add_item({"id": "iron_ore", "name": "Iron Ore", "qty": 2}, merge=True)
    context.add_item({"id": "coal", "name": "Coal", "qty": 1}, merge=True)
    baseline_inventory = [(item.item_def_id, int(getattr(item, "quantity", 1))) for item in context.player.inventory]

    result = runtime.run_command(context.campaign_id, "craft iron bar")

    assert result["command_type"] == "craft"
    assert result["hours_advanced"] == 0
    assert "nearby forge" in result["narrative"].lower()
    assert [(item.item_def_id, int(getattr(item, "quantity", 1))) for item in context.player.inventory] == baseline_inventory
    assert player.xp == 0
    assert isinstance(result["campaign"]["player"], dict)


def test_run_command_craft_with_nearby_workstation_succeeds() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.skills["smithing"] = 15
    player.xp = 0
    context.position = [0, 0]
    context.player_entity.position = (0, 0)
    _add_workstation(context, workstation_id="test_forge", name="Travel Forge")
    context.add_item({"id": "iron_ore", "name": "Iron Ore", "qty": 2}, merge=True)
    context.add_item({"id": "coal", "name": "Coal", "qty": 1}, merge=True)

    result = runtime.run_command(context.campaign_id, "craft iron bar")

    assert result["command_type"] == "craft"
    assert result["hours_advanced"] == 2
    assert "crafted" in result["narrative"].lower()
    assert context.find_inventory_item("iron_bar") is not None
    assert player.xp > 0
    assert isinstance(result["campaign"]["player"], dict)


def test_run_command_craft_any_recipe_works_without_workstation(monkeypatch) -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.xp = 0
    context.position = [0, 0]
    context.player_entity.position = (0, 0)
    context.add_item({"id": "coal", "name": "Coal", "qty": 1}, merge=True)
    recipe_bank = dict(gameplay_bridge.recipes_registry())
    recipe_bank["trail_token"] = {
        "id": "trail_token",
        "name": "Trail Token",
        "workstation": "any",
        "skill": "",
        "skill_dc": 0,
        "ingredients": [{"item_id": "coal", "quantity": 1}],
        "products": [{"item_id": "iron_ore", "quantity": 1}],
        "xp_reward": 3,
    }
    monkeypatch.setattr(gameplay_bridge, "recipes_registry", lambda: recipe_bank)

    result = runtime.run_command(context.campaign_id, "craft trail token")

    assert result["command_type"] == "craft"
    assert result["hours_advanced"] == 2
    assert "crafted" in result["narrative"].lower()
    assert context.find_inventory_item("iron_ore") is not None
    assert player.xp == 3


def test_run_command_craft_repeated_missing_workstation_stays_non_mutating() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.skills["smithing"] = 15
    player.xp = 0
    context.position = [0, 0]
    context.player_entity.position = (0, 0)
    context.add_item({"id": "iron_ore", "name": "Iron Ore", "qty": 2}, merge=True)
    context.add_item({"id": "coal", "name": "Coal", "qty": 1}, merge=True)
    baseline_inventory = [(item.item_def_id, int(getattr(item, "quantity", 1))) for item in context.player.inventory]

    first = runtime.run_command(context.campaign_id, "craft iron bar")
    second = runtime.run_command(context.campaign_id, "craft iron bar")

    assert first["command_type"] == "craft"
    assert second["command_type"] == "craft"
    assert first["hours_advanced"] == 0
    assert second["hours_advanced"] == 0
    assert "nearby forge" in first["narrative"].lower()
    assert "nearby forge" in second["narrative"].lower()
    assert [(item.item_def_id, int(getattr(item, "quantity", 1))) for item in context.player.inventory] == baseline_inventory
    assert player.xp == 0


def test_run_command_long_rest_repeatedly_hits_cooldown() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.raw_payload["game_tick"] = 100
    player.stats["hp"] = max(1, int(player.stats.get("max_hp", 20)) // 2)

    first = runtime.run_command(context.campaign_id, "long rest")
    second = runtime.run_command(context.campaign_id, "long rest")

    assert first["command_type"] == "rest"
    assert first["hours_advanced"] == 8
    assert "cannot take a long rest yet" in second["narrative"].lower()
    assert second["hours_advanced"] == 0


def test_run_command_cast_repeatedly_until_insufficient_points() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.spell_points = 4
    player.raw_payload["max_spell_points"] = 4
    player.raw_payload["game_tick"] = 100

    first = runtime.run_command(context.campaign_id, "cast magic missile")
    player.raw_payload["game_tick"] = 106
    second = runtime.run_command(context.campaign_id, "cast magic missile")
    player.raw_payload["game_tick"] = 112
    third = runtime.run_command(context.campaign_id, "cast magic missile")

    assert first["command_type"] == "spell"
    assert second["command_type"] == "spell"
    assert "not enough spell points" in third["narrative"].lower()
    assert player.spell_points == 0


def test_progression_command_reports_current_spend_counters() -> None:
    runtime, context = _make_campaign()
    _set_progression_state(context, skill_points=2, proficiency_points=1, ability_increases=1)

    result = runtime.run_command(context.campaign_id, "progression")

    assert result["command_type"] == "progression"
    assert "2 skill points" in result["narrative"].lower()
    progression = result["campaign"]["character_sheet"]["progression"]
    assert progression["skill_points_available"] == 2
    assert progression["proficiency_points_available"] == 1
    assert progression["ability_increases_available"] == 1


def test_train_skill_spends_point_and_updates_character_sheet() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.skills["athletics"] = 1
    _set_progression_state(context, skill_points=2)

    result = runtime.run_command(context.campaign_id, "train athletics")

    assert result["command_type"] == "progression"
    assert player.skills["athletics"] == 2
    assert result["campaign"]["character_sheet"]["progression"]["skill_points_available"] == 1


def test_proficiency_and_expertise_update_skill_flags_and_persist() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.skills["survival"] = 2
    _set_progression_state(context, proficiency_points=2)

    proficiency = runtime.run_command(context.campaign_id, "proficiency survival")
    expertise = runtime.run_command(context.campaign_id, "expertise survival")

    assert proficiency["command_type"] == "progression"
    assert expertise["command_type"] == "progression"
    sheet_skills = {entry["id"]: entry for entry in expertise["campaign"]["character_sheet"]["skills"]}
    assert "survival" in player.raw_payload["skill_proficiencies"]
    assert "survival" in player.raw_payload["expertise_skills"]
    assert sheet_skills["survival"]["proficient"] is True
    assert sheet_skills["survival"]["expertise"] is True
    assert expertise["campaign"]["character_sheet"]["progression"]["proficiency_points_available"] == 0

    runtime.save_campaign(context.campaign_id, "progression_skill_slot", "RuntimeTester")
    loaded = runtime.load_campaign("progression_skill_slot")
    loaded_player = loaded.kernel_runtime["actors"]["player"]
    assert "survival" in loaded_player.raw_payload["skill_proficiencies"]
    assert "survival" in loaded_player.raw_payload["expertise_skills"]


def test_raise_ability_spends_counter_and_updates_modifier() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    original_mig = int(player.stats.get("MIG", 10))
    _set_progression_state(context, ability_increases=1)

    result = runtime.run_command(context.campaign_id, "raise mig")

    assert result["command_type"] == "progression"
    assert int(player.stats.get("MIG", 10)) == original_mig + 1
    mig_row = next(entry for entry in result["campaign"]["character_sheet"]["stats"] if entry["id"] == "MIG")
    assert mig_row["value"] == original_mig + 1
    assert result["campaign"]["character_sheet"]["progression"]["ability_increases_available"] == 0


def test_progression_failures_are_non_mutating() -> None:
    runtime, context = _make_campaign()
    player = context.kernel_runtime["actors"]["player"]
    player.skills["survival"] = 1
    baseline_mig = int(player.stats.get("MIG", 10))
    _set_progression_state(context)

    train = runtime.run_command(context.campaign_id, "train survival")
    expertise = runtime.run_command(context.campaign_id, "expertise survival")
    raise_stat = runtime.run_command(context.campaign_id, "raise mig")

    assert "no skill points available" in train["narrative"].lower()
    assert "need proficiency" in expertise["narrative"].lower()
    assert "no ability increases available" in raise_stat["narrative"].lower()
    assert player.skills["survival"] == 1
    assert int(player.stats.get("MIG", 10)) == baseline_mig


def test_recruit_companion_save_load_preserves_party_membership() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_scout", name="Scout Mira", role="scout")

    recruit = maybe_handle_party_command(context, "recruit Scout Mira")
    assert recruit is not None
    assert recruit[1] == "party"

    runtime.save_campaign(context.campaign_id, "party_recruit_slot", "RuntimeTester")
    loaded = runtime.load_campaign("party_recruit_slot")

    assert "player" in loaded.campaign_state["party"]
    assert companion.identity.actor_id in loaded.campaign_state["party"]
    payload = runtime.snapshot(loaded.campaign_id, narrative="loaded")
    assert companion.identity.actor_id in payload["campaign"]["party"]


def test_dismiss_companion_save_load_removes_party_membership() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_warden", name="Warden Holt", role="guard")

    assert maybe_handle_party_command(context, "recruit Warden Holt") is not None
    dismiss = maybe_handle_party_command(context, "dismiss Warden Holt")

    assert dismiss is not None
    assert dismiss[1] == "party"
    runtime.save_campaign(context.campaign_id, "party_dismiss_slot", "RuntimeTester")
    loaded = runtime.load_campaign("party_dismiss_slot")

    assert companion.identity.actor_id not in loaded.campaign_state["party"]
    payload = runtime.snapshot(loaded.campaign_id, narrative="loaded")
    assert companion.identity.actor_id not in payload["campaign"]["party"]


def test_party_members_do_not_break_campaign_payload_shape() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_mage", name="Mage Elira", role="mage")
    assert maybe_handle_party_command(context, "recruit Mage Elira") is not None

    payload = runtime.snapshot(context.campaign_id, narrative="party")

    assert payload["campaign"]["party"][0] == "player"
    assert companion.identity.actor_id in payload["campaign"]["party"]
    assert isinstance(payload["campaign"]["world_entities"], list)
    assert isinstance(payload["campaign"]["player"], dict)


def test_duplicate_recruit_does_not_duplicate_party_ids() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_blade", name="Blade Nera", role="guard")

    first = runtime.run_command(context.campaign_id, "recruit Blade Nera")
    second = runtime.run_command(context.campaign_id, "recruit Blade Nera")

    party = context.kernel_runtime["game_state"].party
    assert first["command_type"] == "party"
    assert second["command_type"] == "party"
    assert "already in the party" in second["narrative"].lower()
    assert party.count(companion.identity.actor_id) == 1
    assert first["campaign"]["party"].count(companion.identity.actor_id) == 1
    assert second["campaign"]["party"].count(companion.identity.actor_id) == 1


def test_cannot_dismiss_player() -> None:
    runtime, context = _make_campaign()

    result = runtime.run_command(context.campaign_id, "dismiss RuntimeTester")

    assert result["command_type"] == "party"
    assert "cannot dismiss the player" in result["narrative"].lower()
    assert context.kernel_runtime["game_state"].party == ["player"]


def test_recruit_hostile_and_invalid_actor_fail_safely() -> None:
    runtime, context = _make_campaign()
    hostile = _inject_companion(context, base_id="companion_raider", name="Raider Voss", role="raider", hostile=True)

    hostile_result = runtime.run_command(context.campaign_id, f"recruit {hostile.identity.display_name}")
    invalid_result = runtime.run_command(context.campaign_id, "recruit Nobody Here")

    assert hostile_result["command_type"] == "party"
    assert "hostile" in hostile_result["narrative"].lower()
    assert hostile.identity.actor_id not in context.kernel_runtime["game_state"].party
    assert invalid_result["command_type"] == "party"
    assert "no recruitable companion matched" in invalid_result["narrative"].lower()


def test_region_projection_rebuild_preserves_allied_party_members() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_mapscout", name="Map Scout Iven", role="scout")

    assert runtime.run_command(context.campaign_id, "recruit Map Scout Iven")["command_type"] == "party"
    refreshed = runtime.run_command(context.campaign_id, "look around")

    assert refreshed["command_type"] == "exploration"
    assert companion.identity.actor_id in context.kernel_runtime["game_state"].party
    record = context.entities.get(companion.identity.actor_id)
    assert record is not None
    assert record.get("attitude") == "ally"
    assert record.get("disposition") == "ally"
    assert companion.identity.actor_id in refreshed["campaign"]["party"]


def test_party_payload_remains_deduplicated_and_stable() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_dupe", name="Dorian Pike", role="guard")

    assert runtime.run_command(context.campaign_id, "recruit Dorian Pike")["command_type"] == "party"
    context.kernel_runtime["game_state"].party = ["player", companion.identity.actor_id, companion.identity.actor_id, "player"]
    context.kernel_runtime["game_state"].inactive_npcs = [companion.identity.actor_id, companion.identity.actor_id, "player"]

    payload = runtime.snapshot(context.campaign_id, narrative="party")

    assert payload["campaign"]["party"] == ["player", companion.identity.actor_id]
    assert context.kernel_runtime["game_state"].party == ["player", companion.identity.actor_id]
    assert companion.identity.actor_id not in context.kernel_runtime["game_state"].inactive_npcs


def test_party_swap_requires_valid_active_and_inactive_companions() -> None:
    runtime, context = _make_campaign()
    active = _inject_companion(context, base_id="companion_active", name="Active Rill", role="guard")
    reserve = _inject_companion(context, base_id="companion_reserve", name="Reserve Vale", role="scout")

    assert runtime.run_command(context.campaign_id, "recruit Active Rill")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "recruit Reserve Vale")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "dismiss Reserve Vale")["command_type"] == "party"

    invalid = runtime.run_command(context.campaign_id, "swap RuntimeTester with Reserve Vale")
    swapped = runtime.run_command(context.campaign_id, "swap Active Rill with Reserve Vale")

    assert invalid["command_type"] == "party"
    assert "requires one active companion and one inactive companion" in invalid["narrative"].lower()
    assert swapped["command_type"] == "party"
    assert "swaps in" in swapped["narrative"].lower()
    assert context.kernel_runtime["game_state"].party == ["player", reserve.identity.actor_id]
    assert active.identity.actor_id in context.kernel_runtime["game_state"].inactive_npcs
    assert reserve.identity.actor_id not in context.kernel_runtime["game_state"].inactive_npcs


def test_region_projection_uses_active_formation_slots_only() -> None:
    runtime, context = _make_campaign()
    alpha = _inject_companion(context, base_id="companion_alpha", name="Alpha Venn", role="guard")
    beta = _inject_companion(context, base_id="companion_beta", name="Beta Iri", role="scout")
    reserve = _inject_companion(context, base_id="companion_gamma", name="Gamma Sol", role="mage")

    assert runtime.run_command(context.campaign_id, "recruit Alpha Venn")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "recruit Beta Iri")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "recruit Gamma Sol")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "dismiss Gamma Sol")["command_type"] == "party"
    formation_result = runtime.run_command(context.campaign_id, "formation line")
    refreshed = runtime.run_command(context.campaign_id, "look around")

    assert formation_result["command_type"] == "party"
    offsets = FORMATIONS["line"]
    player_x, player_y = int(context.position[0]), int(context.position[1])
    alpha_record = context.entities.get(alpha.identity.actor_id)
    beta_record = context.entities.get(beta.identity.actor_id)
    reserve_record = context.entities.get(reserve.identity.actor_id)
    assert alpha_record is not None
    assert beta_record is not None
    assert alpha_record.get("position") == [player_x + offsets[1][0], player_y + offsets[1][1]]
    assert beta_record.get("position") == [player_x + offsets[2][0], player_y + offsets[2][1]]
    assert alpha_record.get("attitude") == "ally"
    assert beta_record.get("disposition") == "ally"
    assert reserve_record is None or reserve_record.get("attitude") != "ally"
    assert refreshed["command_type"] == "exploration"


def test_formation_changes_remain_stable_through_save_load() -> None:
    runtime, context = _make_campaign()
    companion = _inject_companion(context, base_id="companion_save", name="Save Piper", role="scout")

    assert runtime.run_command(context.campaign_id, "recruit Save Piper")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "formation scatter")["command_type"] == "party"

    runtime.save_campaign(context.campaign_id, "party_formation_slot", "RuntimeTester")
    loaded = runtime.load_campaign("party_formation_slot")
    refreshed = runtime.run_command(loaded.campaign_id, "look around")

    assert loaded.kernel_runtime["game_state"].formation == "scatter"
    offsets = FORMATIONS["scatter"]
    player_x, player_y = int(loaded.position[0]), int(loaded.position[1])
    record = loaded.entities.get(companion.identity.actor_id)
    assert record is not None
    assert record.get("position") == [player_x + offsets[1][0], player_y + offsets[1][1]]
    assert companion.identity.actor_id in refreshed["campaign"]["party"]


def test_swap_and_projection_do_not_create_duplicate_or_overlapping_active_party_state() -> None:
    runtime, context = _make_campaign()
    active = _inject_companion(context, base_id="companion_slot_a", name="Slot A", role="guard")
    reserve = _inject_companion(context, base_id="companion_slot_b", name="Slot B", role="scout")

    assert runtime.run_command(context.campaign_id, "recruit Slot A")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "recruit Slot B")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "dismiss Slot B")["command_type"] == "party"
    assert runtime.run_command(context.campaign_id, "swap Slot A with Slot B")["command_type"] == "party"

    refreshed = runtime.run_command(context.campaign_id, "look around")
    party = context.kernel_runtime["game_state"].party
    active_positions = []
    for actor_id in party[1:]:
        record = context.entities.get(actor_id)
        assert record is not None
        active_positions.append(tuple(record.get("position", [])))

    assert refreshed["command_type"] == "exploration"
    assert party == ["player", reserve.identity.actor_id]
    assert len(active_positions) == len(set(active_positions))
    assert active.identity.actor_id not in party


def test_time_advancement_changes_scheduled_npc_projected_position_and_activity() -> None:
    runtime, context = _make_campaign()
    entity_id, record = _first_scheduled_npc(context)
    entries = _schedule_entries(record)
    context.world.simulation_snapshot.current_hour = 7
    context.world.simulation_snapshot.current_day = 1

    result = runtime.run_command(context.campaign_id, "rest")
    record = context.entities[entity_id]
    expected = _expected_schedule_entry(entries, result["campaign"]["world"]["current_hour"])

    assert result["command_type"] == "rest"
    assert record.get("position") == list(expected.get("position", record.get("position", [])))
    assert record.get("assignment") == str(expected.get("activity"))
    assert record.get("activity") == str(expected.get("activity"))


def test_schedule_wraparound_across_midnight_uses_last_entry_before_hour() -> None:
    runtime, context = _make_campaign()
    entity_id, record = _first_scheduled_npc(context)
    entries = _schedule_entries(record)
    context.world.simulation_snapshot.current_hour = 23
    context.world.simulation_snapshot.current_day = 1

    result = runtime.run_command(context.campaign_id, "rest")
    record = context.entities[entity_id]
    expected = _expected_schedule_entry(entries, result["campaign"]["world"]["current_hour"])

    assert result["command_type"] == "rest"
    assert record.get("position") == list(expected.get("position", record.get("position", [])))
    assert record.get("assignment") == str(expected.get("activity"))


def test_party_members_are_not_overwritten_by_schedule_motion() -> None:
    runtime, context = _make_campaign()
    entity_id, record = _first_scheduled_npc(context)
    companion_name = str(record.get("name", entity_id))
    recruited = runtime.run_command(context.campaign_id, f"recruit {companion_name}")
    context.world.simulation_snapshot.current_hour = 7
    result = runtime.run_command(context.campaign_id, "rest")
    record = context.entities[entity_id]
    player_x, player_y = int(context.position[0]), int(context.position[1])
    offsets = FORMATIONS[context.kernel_runtime["game_state"].formation]

    assert recruited["command_type"] == "party"
    assert result["command_type"] == "rest"
    assert record.get("position") == [player_x + offsets[1][0], player_y + offsets[1][1]]
    assert record.get("attitude") == "ally"


def test_save_load_preserves_schedule_backed_projected_state() -> None:
    runtime, context = _make_campaign()
    entity_id, record = _first_scheduled_npc(context)
    entries = _schedule_entries(record)
    context.world.simulation_snapshot.current_hour = 7
    runtime.run_command(context.campaign_id, "rest")
    projected = context.entities[entity_id]

    runtime.save_campaign(context.campaign_id, "schedule_projection_slot", "RuntimeTester")
    loaded = runtime.load_campaign("schedule_projection_slot")
    loaded_record = loaded.entities.get(entity_id)
    expected = _expected_schedule_entry(entries, int(loaded.world.simulation_snapshot.current_hour))

    assert loaded_record is not None
    assert projected.get("position") == list(expected.get("position", projected.get("position", [])))
    assert loaded_record.get("position") == projected.get("position")
    assert loaded_record.get("assignment") == projected.get("assignment")


def test_missing_schedule_positions_remain_non_crashing_and_non_destructive() -> None:
    runtime, context = _make_campaign()
    entity_id, record = _first_scheduled_npc(context)
    baseline_position = list(record.get("position", []))
    _set_npc_schedule(
        context,
        entity_id,
        [
            {"hour": 0, "position": [1, 1], "activity": "sleep"},
            {"hour": 8, "activity": "idle_watch"},
        ],
    )
    context.world.simulation_snapshot.current_hour = 7
    context.world.simulation_snapshot.current_day = 1

    sync_context_clock(context)
    record = context.entities[entity_id]

    assert record.get("position") == [1, 1]
    assert record.get("assignment") == "sleep"

    context.world.simulation_snapshot.current_hour = 8
    sync_context_clock(context)
    record = context.entities[entity_id]

    assert record.get("position") == [1, 1]
    assert record.get("assignment") == "idle_watch"
