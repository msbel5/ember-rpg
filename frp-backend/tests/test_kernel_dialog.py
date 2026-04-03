from __future__ import annotations

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord, ItemStack
from engine.kernel.dialog import (
    DialogAction,
    DialogCondition,
    DialogDef,
    DialogStateNode,
    DialogTransition,
    compute_npc_reaction,
    evaluate_condition,
    execute_dialog_action,
    get_available_transitions,
    select_transition,
    start_dialog,
)


def _actor(actor_id: str, *, cha: int = 10, strength: int = 10) -> ActorRecord:
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="npc", faction_id="settlement"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"PRE": cha, "MIG": strength},
        raw_payload={"relationship_score": 0, "quests": {}, "journal": [], "spawned_creatures": []},
    )


def test_ac01_start_dialog_returns_first_valid_state():
    dialog = DialogDef(
        dialog_id="npc_a",
        npc_id="npc_a",
        states=[
            DialogStateNode(
                state_id="blocked",
                text="Blocked",
                trigger=DialogCondition("stat_check", {"actor": "player", "stat": "PRE", "operator": ">=", "value": 20}),
            ),
            DialogStateNode(state_id="intro", text="Hello there."),
            DialogStateNode(state_id="later", text="Later."),
        ],
    )

    state, node, _ = start_dialog(dialog, _actor("npc"), _actor("player", cha=14), {})

    assert state.current_state_id == "intro"
    assert node.state_id == "intro"


def test_ac02_cha_gated_transition_hidden_when_player_fails_requirement():
    state = DialogStateNode(
        state_id="intro",
        text="Hello",
        transitions=[
            DialogTransition(
                transition_id="cha_gate",
                text="Persuade",
                condition=DialogCondition("stat_check", {"actor": "player", "stat": "PRE", "operator": ">=", "value": 16}),
            )
        ],
    )

    transitions = get_available_transitions(state, _actor("player", cha=14), _actor("npc"), {}, {})

    assert transitions == []


def test_ac03_cha_gated_transition_visible_when_player_meets_requirement():
    state = DialogStateNode(
        state_id="intro",
        text="Hello",
        transitions=[
            DialogTransition(
                transition_id="cha_gate",
                text="Persuade",
                condition=DialogCondition("stat_check", {"actor": "player", "stat": "PRE", "operator": ">=", "value": 16}),
            )
        ],
    )

    transitions = get_available_transitions(state, _actor("player", cha=18), _actor("npc"), {}, {})

    assert [transition.transition_id for transition in transitions] == ["cha_gate"]


def test_ac04_give_item_action_adds_item_to_player_inventory():
    player = _actor("player")
    npc = _actor("npc")

    execute_dialog_action(DialogAction("give_item", {"item_def_id": "healing_potion", "quantity": 1}), player, npc, {}, {})

    assert any(item.item_def_id == "healing_potion" for item in player.inventory)


def test_ac05_set_variable_action_updates_local_dialog_variables():
    player = _actor("player")
    npc = _actor("npc")
    variables: dict[str, object] = {}

    execute_dialog_action(DialogAction("set_variable", {"scope": "local", "name": "talked_once", "value": True}), player, npc, variables, {})

    assert variables["talked_once"] is True


def test_ac06_terminating_transition_deactivates_dialog():
    player = _actor("player")
    npc = _actor("npc")
    dialog = DialogDef(
        dialog_id="npc_a",
        npc_id="npc",
        states=[DialogStateNode(state_id="intro", text="Hello", transitions=[])],
    )
    dialog_state, _, _ = start_dialog(dialog, npc, player, {})
    transition = DialogTransition(transition_id="bye", text="Bye", terminates=True)

    updated, next_state, _ = select_transition(dialog_state, transition, {"npc_a": dialog}, player, npc, {})

    assert updated.active is False
    assert next_state is None


def test_ac07_compute_npc_reaction_uses_cha_reputation_and_relationship():
    player = _actor("player", cha=18)
    npc = _actor("npc")

    reaction = compute_npc_reaction(player, npc, reputation=15)

    assert reaction == 31


def test_ac08_transition_can_jump_to_another_dialog_tree():
    player = _actor("player")
    npc = _actor("npc")
    dialog_a = DialogDef(
        dialog_id="npc_a_dialog",
        npc_id="npc",
        states=[
            DialogStateNode(
                state_id="intro",
                text="Ask my colleague.",
                transitions=[
                    DialogTransition(
                        transition_id="jump",
                        text="Go on",
                        next_dialog_id="npc_b_dialog",
                        next_state_id="intro_b",
                    )
                ],
            )
        ],
    )
    dialog_b = DialogDef(
        dialog_id="npc_b_dialog",
        npc_id="npc_b",
        states=[DialogStateNode(state_id="intro_b", text="I am the colleague.")],
    )
    dialog_state, _, transitions = start_dialog(dialog_a, npc, player, {})

    updated, next_state, _ = select_transition(dialog_state, transitions[0], {"npc_a_dialog": dialog_a, "npc_b_dialog": dialog_b}, player, npc, {})

    assert updated.dialog_id == "npc_b_dialog"
    assert next_state is not None and next_state.state_id == "intro_b"


def test_ac09_composite_and_condition_requires_all_children():
    player = _actor("player", strength=16)
    player.inventory.append(ItemStack(instance_id="item_1", item_def_id="magic_key"))
    condition = DialogCondition(
        "and",
        children=[
            DialogCondition("stat_check", {"actor": "player", "stat": "MIG", "operator": ">=", "value": 14}),
            DialogCondition("item_check", {"actor": "player", "item_def_id": "magic_key"}),
        ],
    )

    assert evaluate_condition(condition, player, _actor("npc"), {}, {}) is True


def test_ac10_dialog_def_round_trip_preserves_nested_structure():
    dialog = DialogDef(
        dialog_id="npc_dialog",
        npc_id="npc",
        states=[
            DialogStateNode(
                state_id="intro",
                text="Hello",
                transitions=[
                    DialogTransition(
                        transition_id="reply",
                        text="Hi",
                        condition=DialogCondition("variable_check", {"scope": "global", "name": "met", "operator": "==", "value": True}),
                        actions=[DialogAction("set_variable", {"scope": "local", "name": "talked", "value": True})],
                        next_state_id="end",
                    )
                ],
            ),
            DialogStateNode(state_id="end", text="Goodbye"),
        ],
        initial_variables={"talked": False},
    )

    restored = DialogDef.from_dict(dialog.to_dict())

    assert restored == dialog
