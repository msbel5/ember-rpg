from __future__ import annotations

from engine.kernel.actor import (
    ActorIdentity,
    ActorPosition,
    ActorRecord,
    BodyPartDef,
    BodyPartState,
    BodyPlanDef,
    BodyState,
    EquipmentLoadout,
    ItemStack,
    TissueLayerDef,
    WoundRecord,
)
from engine.kernel.effects import (
    EffectDef,
    EffectInstance,
    EffectQueue,
    apply_effect,
    check_resistance,
    compute_effective_stat,
    dispel_effects,
    resolve_saving_throw,
    tick_effects,
)


def _body_state() -> BodyState:
    plan = BodyPlanDef(
        plan_id="humanoid",
        label="Humanoid",
        parts=[
            BodyPartDef(
                part_id="torso",
                label="Torso",
                max_hp=12,
                vital=True,
                relative_size=12,
                layers=[
                    TissueLayerDef("skin", "skin", relative_thickness=2, under_pressure=True),
                    TissueLayerDef("muscle", "muscle", relative_thickness=2),
                    TissueLayerDef("organs", "organ", relative_thickness=2, vital=True),
                ],
            ),
            BodyPartDef(
                part_id="chest",
                label="Chest",
                max_hp=10,
                vital=True,
                relative_size=10,
                layers=[
                    TissueLayerDef("skin", "skin", relative_thickness=2, under_pressure=True),
                    TissueLayerDef("ribcage", "bone", relative_thickness=2, structural=True),
                    TissueLayerDef("lungs", "organ", relative_thickness=2, vital=True),
                ],
            ),
        ],
    )
    return BodyState(
        plan=plan,
        parts={
            "torso": BodyPartState(part_id="torso", current_hp=12, max_hp=12),
            "chest": BodyPartState(part_id="chest", current_hp=10, max_hp=10),
        },
    )


def _actor(
    *,
    stats: dict[str, int] | None = None,
    save_bonuses: dict[str, int] | None = None,
    inventory: list[ItemStack] | None = None,
    equipment: EquipmentLoadout | None = None,
) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id="actor_1", display_name="Actor", actor_type="npc"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats=stats or {"STR": 14, "DEX": 12, "CON": 12, "WIS": 10, "hp": 20, "max_hp": 20},
        skills={},
        body_state=_body_state(),
        inventory=inventory or [],
        equipment=equipment or EquipmentLoadout(),
        raw_payload={"save_bonuses": save_bonuses or {}},
    )


def _effect_def(**overrides) -> EffectDef:
    payload = {
        "effect_def_id": "effect_1",
        "label": "Effect One",
        "category": "stat_mod",
        "target_stat": "STR",
        "modifier_type": "flat",
        "modifier_value": 4.0,
        "timing_mode": "duration",
        "base_duration_ticks": 10,
        "max_stacks": 2,
        "saving_throw_type": "none",
        "saving_throw_dc": 0,
        "delivery": "direct",
        "resistance_stat": "",
        "resistance_dc": 0,
        "tags": [],
    }
    payload.update(overrides)
    return EffectDef(**payload)


def _effect_queue(actor: ActorRecord, *instances: EffectInstance) -> EffectQueue:
    queue = EffectQueue(actor_id=actor.identity.actor_id, instances=list(instances))
    queue.rebuild_condition_cache()
    actor.effect_queue = queue
    return queue


def test_effect_def_round_trips_without_loss():
    effect_def = _effect_def(tags=["magic", "buff"], source_type="spell")

    restored = EffectDef.from_dict(effect_def.to_dict())

    assert restored == effect_def


def test_apply_effect_marks_instance_saved_when_save_passes_exact_dc():
    actor = _actor(stats={"WIS": 10, "hp": 20, "max_hp": 20}, save_bonuses={"will": 3})
    effect = _effect_def(saving_throw_type="will", saving_throw_dc=15)

    applied, instance = apply_effect(actor, effect, source_id="spell_1", current_tick=4, d20_roll=12)

    assert applied is True
    assert instance is not None
    assert instance.saved is True


def test_condition_effect_is_negated_on_save_but_stat_mod_is_halved():
    actor = _actor(stats={"WIS": 10, "STR": 14, "hp": 20, "max_hp": 20}, save_bonuses={"will": 3})
    condition = _effect_def(
        effect_def_id="hold",
        category="condition",
        condition_flag="stunned",
        saving_throw_type="will",
        saving_throw_dc=15,
    )
    stat_mod = _effect_def(
        effect_def_id="bless",
        category="stat_mod",
        modifier_value=4.0,
        saving_throw_type="will",
        saving_throw_dc=15,
    )

    applied_condition, _ = apply_effect(actor, condition, source_id="spell_hold", current_tick=1, d20_roll=12)
    applied_stat, stat_instance = apply_effect(actor, stat_mod, source_id="spell_bless", current_tick=2, d20_roll=12)

    assert applied_condition is False
    assert applied_stat is True
    assert stat_instance is not None and stat_instance.saved is True
    assert compute_effective_stat(actor, "STR") == 16


def test_tick_effects_expires_duration_effects():
    actor = _actor()
    effect = _effect_def(base_duration_ticks=10)
    instance = EffectInstance(
        instance_id="i1",
        effect_def_id=effect.effect_def_id,
        effect_def=effect,
        source_id="source_a",
        target_id=actor.identity.actor_id,
        ticks_remaining=3,
        tick_applied=0,
    )
    _effect_queue(actor, instance)

    tick_effects(actor, 1)
    tick_effects(actor, 2)
    tick_effects(actor, 3)

    assert actor.effect_queue is not None
    assert actor.effect_queue.instances == []


def test_same_source_refreshes_duration_without_adding_stack():
    actor = _actor()
    effect = _effect_def(base_duration_ticks=10)
    applied, instance = apply_effect(actor, effect, source_id="source_a", current_tick=1)
    assert applied is True
    assert instance is not None
    instance.ticks_remaining = 5

    applied_again, _ = apply_effect(actor, effect, source_id="source_a", current_tick=2)

    assert applied_again is True
    assert len(actor.effect_queue.instances) == 1
    assert actor.effect_queue.instances[0].ticks_remaining == 10


def test_different_sources_stack_until_max_stacks():
    actor = _actor()
    effect = _effect_def(base_duration_ticks=10, max_stacks=3)

    apply_effect(actor, effect, source_id="source_a", current_tick=1)
    apply_effect(actor, effect, source_id="source_b", current_tick=2)

    assert len(actor.effect_queue.instances) == 2
    assert {item.source_id for item in actor.effect_queue.instances} == {"source_a", "source_b"}


def test_overflow_refreshes_oldest_instance_instead_of_adding_new_one():
    actor = _actor()
    effect = _effect_def(base_duration_ticks=10, max_stacks=2)

    apply_effect(actor, effect, source_id="source_a", current_tick=1)
    apply_effect(actor, effect, source_id="source_b", current_tick=2)
    actor.effect_queue.instances[0].ticks_remaining = 1

    apply_effect(actor, effect, source_id="source_c", current_tick=3)

    assert len(actor.effect_queue.instances) == 2
    assert actor.effect_queue.instances[0].source_id == "source_c"
    assert actor.effect_queue.instances[0].ticks_remaining == 10


def test_compute_effective_stat_prefers_set_override_over_other_modifiers():
    actor = _actor(stats={"STR": 14, "hp": 20, "max_hp": 20})
    effects = [
        EffectInstance("a", "flat_2", _effect_def(effect_def_id="flat_2", modifier_value=2), "a", actor.identity.actor_id),
        EffectInstance("b", "flat_3", _effect_def(effect_def_id="flat_3", modifier_value=3), "b", actor.identity.actor_id),
        EffectInstance("c", "pct_25", _effect_def(effect_def_id="pct_25", modifier_type="percentage", modifier_value=25), "c", actor.identity.actor_id),
        EffectInstance("d", "set_20", _effect_def(effect_def_id="set_20", modifier_type="set", modifier_value=20), "d", actor.identity.actor_id),
    ]
    _effect_queue(actor, *effects)

    assert compute_effective_stat(actor, "STR") == 20


def test_compute_effective_stat_applies_flat_then_percentage():
    actor = _actor(stats={"STR": 14, "hp": 20, "max_hp": 20})
    effects = [
        EffectInstance("a", "flat_2", _effect_def(effect_def_id="flat_2", modifier_value=2), "a", actor.identity.actor_id),
        EffectInstance("b", "pct_50", _effect_def(effect_def_id="pct_50", modifier_type="percentage", modifier_value=50), "b", actor.identity.actor_id),
    ]
    _effect_queue(actor, *effects)

    assert compute_effective_stat(actor, "STR") == 24


def test_dot_effect_creates_wound_records_and_halves_when_saved():
    actor = _actor(stats={"hp": 20, "max_hp": 20})
    dot = _effect_def(
        effect_def_id="burning",
        category="dot",
        damage_per_tick=5,
        damage_type="fire",
        target_stat="",
    )
    first = EffectInstance("dot_1", dot.effect_def_id, dot, "source_a", actor.identity.actor_id, saved=False, tick_applied=0)
    second = EffectInstance("dot_2", dot.effect_def_id, dot, "source_b", actor.identity.actor_id, saved=True, tick_applied=0)
    _effect_queue(actor, first, second)

    tick_effects(actor, 1)

    damage_amounts = [wound.damage_amount for wound in actor.body_state.wounds]
    assert 5 in damage_amounts
    assert 2 in damage_amounts


def test_condition_flags_persist_until_all_matching_effects_expire():
    actor = _actor()
    condition_def = _effect_def(
        effect_def_id="stun",
        category="condition",
        condition_flag="stunned",
        target_stat="",
    )
    first = EffectInstance("stun_1", "stun", condition_def, "source_a", actor.identity.actor_id, ticks_remaining=1)
    second = EffectInstance("stun_2", "stun", condition_def, "source_b", actor.identity.actor_id, ticks_remaining=2)
    _effect_queue(actor, first, second)

    assert actor.effect_queue.has_condition("stunned") is True
    tick_effects(actor, 1)
    assert actor.effect_queue.has_condition("stunned") is True
    tick_effects(actor, 2)
    assert actor.effect_queue.has_condition("stunned") is False


def test_while_equipped_effects_drop_after_item_is_unequipped():
    item = ItemStack(
        instance_id="ring_1",
        item_def_id="ring_of_giant_strength",
        payload={"slot": "ring", "coverage": []},
    )
    equipment = EquipmentLoadout(slots={"ring": [item]})
    actor = _actor(stats={"STR": 14, "hp": 20, "max_hp": 20}, inventory=[item], equipment=equipment)
    effect = _effect_def(
        effect_def_id="ring_strength",
        modifier_value=4,
        timing_mode="while_equipped",
    )

    apply_effect(actor, effect, source_id="ring_1", current_tick=0)
    assert compute_effective_stat(actor, "STR") == 18

    actor.equipment.slots["ring"] = []
    tick_effects(actor, 1)

    assert actor.effect_queue.instances == []
    assert compute_effective_stat(actor, "STR") == 14


def test_dispel_by_tag_removes_only_matching_effects():
    actor = _actor()
    magic_a = EffectInstance("m1", "magic_a", _effect_def(effect_def_id="magic_a", tags=["magic"]), "a", actor.identity.actor_id)
    magic_b = EffectInstance("m2", "magic_b", _effect_def(effect_def_id="magic_b", tags=["magic"]), "b", actor.identity.actor_id)
    poison = EffectInstance("p1", "poison", _effect_def(effect_def_id="poison", tags=["poison"]), "c", actor.identity.actor_id)
    _effect_queue(actor, magic_a, magic_b, poison)

    removed = dispel_effects(actor, tag="magic")

    assert len(removed) == 2
    assert [item.effect_def_id for item in actor.effect_queue.instances] == ["poison"]


def test_effect_queue_round_trips_all_instances():
    actor = _actor()
    registry = {}
    instances = []
    for index in range(5):
        effect = _effect_def(effect_def_id=f"effect_{index}", modifier_value=index)
        registry[effect.effect_def_id] = effect
        instances.append(
            EffectInstance(
                instance_id=f"instance_{index}",
                effect_def_id=effect.effect_def_id,
                effect_def=effect,
                source_id=f"source_{index}",
                target_id=actor.identity.actor_id,
                ticks_remaining=10 - index,
                saved=bool(index % 2),
                tick_applied=index,
            )
        )
    queue = _effect_queue(actor, *instances)

    restored = EffectQueue.from_dict(queue.to_dict(), registry)

    assert len(restored.instances) == 5
    assert [item.ticks_remaining for item in restored.instances] == [10, 9, 8, 7, 6]
    assert [item.saved for item in restored.instances] == [False, True, False, True, False]


def test_contact_delivery_is_blocked_by_full_torso_coverage():
    armor = ItemStack(
        instance_id="plate_1",
        item_def_id="full_plate",
        payload={"slot": "armor", "coverage": ["torso"], "coverage_percentage": 100},
    )
    actor = _actor(equipment=EquipmentLoadout(slots={"armor": [armor]}), inventory=[armor])
    effect = _effect_def(effect_def_id="contact_poison", delivery="contact", category="condition", condition_flag="poisoned", target_stat="")

    applied, instance = apply_effect(actor, effect, source_id="poison_1", current_tick=0)

    assert applied is False
    assert instance is None


def test_injected_delivery_requires_open_wound():
    actor = _actor()
    effect = _effect_def(effect_def_id="venom", delivery="injected", category="condition", condition_flag="poisoned", target_stat="")

    applied, instance = apply_effect(actor, effect, source_id="venom_1", current_tick=0)

    assert applied is False
    assert instance is None


def test_resistance_check_blocks_effect_on_exact_dc():
    actor = _actor(stats={"CON": 16, "hp": 20, "max_hp": 20})

    resisted = check_resistance(actor, "CON", 12, 9)

    assert resisted is True


def test_saving_throw_respects_natural_one_and_natural_twenty():
    actor = _actor(stats={"WIS": 30, "hp": 20, "max_hp": 20}, save_bonuses={"will": 99})

    assert resolve_saving_throw(actor, "will", 1_000, 1) is False
    assert resolve_saving_throw(actor, "will", 1_000, 20) is True
