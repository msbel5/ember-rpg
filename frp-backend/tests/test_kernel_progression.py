from __future__ import annotations

from engine.kernel.progression import (
    ClassDef,
    ProgressionState,
    award_skill_xp,
    award_xp,
    can_level_up,
    compute_bab,
    compute_saves,
    execute_level_up,
    get_skill_level,
    get_skill_level_name,
)


def _class_defs() -> dict[str, ClassDef]:
    fighter_xp = [0, 2000, 4000, 8000, 16000, 32000, 64000, 125000, 250000, 500000]
    thief_xp = [0, 1250, 2500, 5000, 10000, 20000, 40000, 70000, 110000, 160000]
    mage_xp = [0, 2500, 5000, 10000, 20000, 40000, 60000, 90000, 135000, 250000]
    cleric_xp = [0, 1500, 3000, 6000, 13000, 27500, 55000, 110000, 225000, 450000]
    return {
        "fighter": ClassDef(
            class_id="fighter",
            label="Fighter",
            hit_die=10,
            bab_rate="full",
            good_saves=["fortitude"],
            proficiency_rate=3,
            skill_points_per_level=0,
            hp_after_cap=3,
            hit_die_cap_level=9,
            xp_table=fighter_xp,
        ),
        "thief": ClassDef(
            class_id="thief",
            label="Thief",
            hit_die=6,
            bab_rate="three_quarter",
            good_saves=["reflex"],
            proficiency_rate=4,
            skill_points_per_level=15,
            hp_after_cap=2,
            hit_die_cap_level=10,
            xp_table=thief_xp,
        ),
        "mage": ClassDef(
            class_id="mage",
            label="Mage",
            hit_die=4,
            bab_rate="half",
            good_saves=["will"],
            proficiency_rate=4,
            skill_points_per_level=4,
            spell_type="wizard",
            hp_after_cap=1,
            hit_die_cap_level=10,
            xp_table=mage_xp,
        ),
        "cleric": ClassDef(
            class_id="cleric",
            label="Cleric",
            hit_die=8,
            bab_rate="three_quarter",
            good_saves=["fortitude", "will"],
            proficiency_rate=4,
            skill_points_per_level=6,
            spell_type="priest",
            hp_after_cap=2,
            hit_die_cap_level=9,
            xp_table=cleric_xp,
        ),
    }


def test_ac01_can_level_up_checks_exact_threshold():
    class_defs = _class_defs()
    progression = ProgressionState(actor_id="a1", xp=7999, level=3, classes=["fighter"], class_levels={"fighter": 3})

    assert can_level_up(progression, class_defs) is False
    progression.xp = 8000
    assert can_level_up(progression, class_defs) is True


def test_ac02_hp_gain_uses_hit_die_plus_con_modifier():
    class_defs = _class_defs()
    progression = ProgressionState(actor_id="a2", xp=8000, level=3, classes=["fighter"], class_levels={"fighter": 3})

    result = execute_level_up(progression, "fighter", class_defs["fighter"], hit_die_roll=7, con_modifier=2)

    assert result.hp_gained == 9


def test_ac03_hp_gain_has_minimum_one():
    class_defs = _class_defs()
    progression = ProgressionState(actor_id="a3", xp=5000, level=1, classes=["mage"], class_levels={"mage": 1})

    result = execute_level_up(progression, "mage", class_defs["mage"], hit_die_roll=2, con_modifier=-1)

    assert result.hp_gained == 1


def test_ac04_bab_progression_matches_class_rates():
    class_defs = _class_defs()

    assert compute_bab({"fighter": 5}, class_defs) == 5
    assert compute_bab({"thief": 8}, class_defs) == 6


def test_ac05_save_progression_uses_good_and_poor_tables():
    class_defs = _class_defs()

    saves = compute_saves({"fighter": 6}, class_defs)

    assert saves["fortitude"] == 5
    assert saves["reflex"] == 2


def test_ac06_ability_increase_only_on_every_fourth_level():
    class_defs = _class_defs()
    level_four = ProgressionState(actor_id="a4", xp=8000, level=3, classes=["fighter"], class_levels={"fighter": 3})
    level_five = ProgressionState(actor_id="a5", xp=16000, level=4, classes=["fighter"], class_levels={"fighter": 4})

    result_four = execute_level_up(level_four, "fighter", class_defs["fighter"], hit_die_roll=5, con_modifier=0)
    result_five = execute_level_up(level_five, "fighter", class_defs["fighter"], hit_die_roll=5, con_modifier=0)

    assert result_four.ability_increase is True
    assert result_five.ability_increase is False


def test_ac07_multiclass_uses_best_bab_and_saves():
    class_defs = _class_defs()

    bab = compute_bab({"fighter": 5, "thief": 3}, class_defs)
    saves = compute_saves({"fighter": 5, "thief": 3}, class_defs)

    assert bab == 5
    assert saves["fortitude"] == 4
    assert saves["reflex"] == 3


def test_ac08_skill_xp_crosses_named_tier_boundary():
    progression = ProgressionState(actor_id="a8")
    progression.skill_xp["mining"] = 2500
    progression.skill_levels["mining"] = get_skill_level(2500)

    assert progression.skill_levels["mining"] == 4
    assert get_skill_level_name(progression.skill_levels["mining"]) == "Skilled"

    new_level = award_skill_xp(progression, "mining", 200)

    assert new_level == 5
    assert get_skill_level_name(new_level) == "Proficient"


def test_ac09_skill_xp_caps_at_grand_master():
    assert get_skill_level(16100) == 14
    assert get_skill_level_name(14) == "Grand Master"


def test_ac10_full_level_up_pipeline_returns_expected_values():
    class_defs = _class_defs()
    progression = ProgressionState(actor_id="a10", xp=8000, level=3, classes=["fighter"], class_levels={"fighter": 3})

    result = execute_level_up(progression, "fighter", class_defs["fighter"], hit_die_roll=6, con_modifier=2)

    assert result.new_level == 4
    assert result.hp_gained == 8
    assert result.bab_new == 4
    assert result.saves_new == {"fortitude": 4, "reflex": 1, "will": 1}
    assert result.proficiency_points == 0
    assert result.skill_points == 0
    assert result.new_spell_slots == {}
    assert result.ability_increase is True


def test_ac11_award_xp_tracks_total_and_source():
    progression = ProgressionState(actor_id="a11")

    award_xp(progression, 125, "combat")

    assert progression.xp == 125
    assert progression.xp_sources["combat"] == 125


def test_ac12_progression_state_round_trip_preserves_all_fields():
    original = ProgressionState(
        actor_id="a12",
        xp=9000,
        xp_sources={"combat": 5000, "quest": 4000},
        level=4,
        classes=["fighter", "thief"],
        class_levels={"fighter": 3, "thief": 1},
        bab=3,
        saves={"fortitude": 4, "reflex": 2, "will": 1},
        proficiency_points_available=1,
        skill_points_available=12,
        ability_increases_available=1,
        skill_xp={"mining": 2700},
        skill_levels={"mining": 5},
    )

    restored = ProgressionState.from_dict(original.to_dict())

    assert restored == original
