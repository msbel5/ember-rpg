"""
Store service dispatcher contract tests.

Proves the centralized dispatch_service path resolves existing service
types (room, identify, healing, repair) identically to the direct
function calls, and that new service types (donation, weapon_training,
mount_rental) can be added without touching parser logic.
"""

from __future__ import annotations

import pytest

from engine.kernel.actor import ActorIdentity, ActorPosition, ActorRecord
from engine.kernel.effects import EffectDef, EffectQueue
from engine.kernel.items import ItemDef, ItemInstance
from engine.kernel.spells import SpellSlot, Spellbook
from engine.kernel.store import (
    StoreDef,
    StoreItem,
    StoreService,
    _SERVICE_HANDLERS,
    dispatch_service,
    register_service_handler,
    rent_room,
)


# ── Fixtures (match existing test_kernel_store.py style) ─────────────


def _actor(
    actor_id: str = "player",
    *,
    gold: int = 100,
    hp: int = 10,
    max_hp: int = 20,
    effect_registry: dict | None = None,
    spellbook: Spellbook | None = None,
) -> ActorRecord:
    raw_payload: dict = {"reputation": 10}
    if effect_registry is not None:
        raw_payload["effect_registry"] = effect_registry
    if spellbook is not None:
        raw_payload["spellbooks"] = {"mage": spellbook}
    return ActorRecord(
        identity=ActorIdentity(actor_id=actor_id, display_name=actor_id, actor_type="pc"),
        position=ActorPosition(x=0, y=0),
        action_points=2,
        max_action_points=2,
        alive=True,
        stats={"gold": gold, "PRE": 10, "hp": hp, "max_hp": max_hp},
        skills={},
        inventory=[],
        effect_queue=EffectQueue(actor_id=actor_id),
        raw_payload=raw_payload,
    )


def _store_with_services(*services: StoreService) -> StoreDef:
    return StoreDef(
        store_id="test_store",
        label="Test Store",
        store_type="shop",
        lore=50,
        services=list(services),
    )


# ── Existing service types still work through dispatcher ─────────────


class TestDispatcherExistingServices:
    """Regression: existing services produce the same results via dispatch_service."""

    def test_room_service_via_dispatcher(self):
        spellbook = Spellbook(
            actor_id="player",
            spell_type="mage",
            slots={1: [SpellSlot(spell_level=1, spell_id="magic_missile", memorized=True, expended=True)]},
        )
        actor = _actor(gold=50, hp=5, spellbook=spellbook)
        store = _store_with_services(
            StoreService(service_id="room_basic", service_type="room", label="Room", price=10, room_quality=1.0),
        )

        ok, msg = dispatch_service(actor, store, "room", "room_basic")

        assert ok is True
        assert actor.stats["hp"] == 20  # full heal from rest
        assert actor.stats["gold"] == 40
        assert spellbook.slots[1][0].expended is False  # refreshed

    def test_healing_service_via_dispatcher(self):
        heal_effect = EffectDef(
            effect_def_id="heal_5",
            label="Heal 5",
            category="healing",
            healing_per_tick=5,
            timing_mode="instant",
        )
        actor = _actor(gold=30, hp=10, effect_registry={"heal_5": heal_effect})
        store = _store_with_services(
            StoreService(service_id="cure", service_type="healing", label="Cure", price=15, effect_id="heal_5"),
        )

        ok, msg = dispatch_service(actor, store, "healing", "cure")

        assert ok is True
        assert actor.stats["hp"] == 15
        assert actor.stats["gold"] == 15

    def test_identify_service_via_dispatcher(self):
        actor = _actor(gold=50)
        store = _store_with_services(
            StoreService(service_id="id_svc", service_type="identify", label="Identify", price=20),
        )
        item_def = ItemDef(
            item_def_id="ring", label="Ring", item_type="equipment",
            item_category="accessory", weight=0.1, base_price=100, lore_to_identify=30,
        )
        item = ItemInstance(instance_id="ring_1", item_def_id="ring")

        ok, msg = dispatch_service(actor, store, "identify", "id_svc", item=item, item_def=item_def)

        assert ok is True
        assert item.identified is True
        assert actor.stats["gold"] == 30

    def test_repair_service_via_dispatcher(self):
        actor = _actor(gold=100)
        store = _store_with_services(
            StoreService(service_id="fix", service_type="repair", label="Repair", price=0),
        )
        item_def = ItemDef(
            item_def_id="armor", label="Armor", item_type="armor",
            item_category="armor", weight=10, base_price=200,
        )
        item = ItemInstance(instance_id="armor_1", item_def_id="armor", wear=50, max_wear=100)

        ok, msg = dispatch_service(actor, store, "repair", "fix", item=item, item_def=item_def)

        assert ok is True
        assert item.wear == 0
        assert "repaired" in msg


# ── Service unavailable paths ────────────────────────────────────────


class TestDispatcherUnavailable:
    def test_missing_service_type_returns_failure(self):
        actor = _actor()
        store = _store_with_services()  # no services

        ok, msg = dispatch_service(actor, store, "room")

        assert ok is False
        assert "unavailable" in msg

    def test_wrong_service_id_returns_failure(self):
        actor = _actor()
        store = _store_with_services(
            StoreService(service_id="room_basic", service_type="room", label="Room", price=10),
        )

        ok, msg = dispatch_service(actor, store, "room", "nonexistent_id")

        assert ok is False


# ── Generic fallback for new service types ───────────────────────────


class TestDispatcherGenericFallback:
    """New service types resolve through the generic gold handler without
    adding parser logic anywhere."""

    def test_donation_service_deducts_gold(self):
        actor = _actor(gold=100)
        store = _store_with_services(
            StoreService(service_id="temple_donation", service_type="donation", label="Temple Donation", price=25),
        )

        ok, msg = dispatch_service(actor, store, "donation", "temple_donation")

        assert ok is True
        assert actor.stats["gold"] == 75
        assert "Temple Donation" in msg

    def test_weapon_training_service_deducts_gold(self):
        actor = _actor(gold=200)
        store = _store_with_services(
            StoreService(service_id="sword_drill", service_type="weapon_training", label="Sword Drill", price=50),
        )

        ok, msg = dispatch_service(actor, store, "weapon_training", "sword_drill")

        assert ok is True
        assert actor.stats["gold"] == 150

    def test_mount_rental_service_deducts_gold(self):
        actor = _actor(gold=80)
        store = _store_with_services(
            StoreService(service_id="horse_rental", service_type="mount_rental", label="Horse Rental", price=30),
        )

        ok, msg = dispatch_service(actor, store, "mount_rental", "horse_rental")

        assert ok is True
        assert actor.stats["gold"] == 50

    def test_generic_fallback_fails_with_insufficient_gold(self):
        actor = _actor(gold=5)
        store = _store_with_services(
            StoreService(service_id="expensive", service_type="donation", label="Grand Donation", price=1000),
        )

        ok, msg = dispatch_service(actor, store, "donation", "expensive")

        assert ok is False
        assert "insufficient gold" in msg

    def test_first_service_of_type_used_when_no_id_given(self):
        actor = _actor(gold=100)
        store = _store_with_services(
            StoreService(service_id="basic_donation", service_type="donation", label="Small Donation", price=10),
            StoreService(service_id="grand_donation", service_type="donation", label="Grand Donation", price=100),
        )

        ok, msg = dispatch_service(actor, store, "donation")

        assert ok is True
        assert actor.stats["gold"] == 90  # first (price=10) was used


# ── Runtime handler registration ─────────────────────────────────────


class TestRegisterServiceHandler:
    """Plugins can register custom handlers at runtime."""

    def test_register_and_dispatch_custom_handler(self):
        results = []

        def _custom_handler(actor, store, service, **kwargs):
            results.append(service.service_id)
            return True, "custom ok"

        register_service_handler("custom_service", _custom_handler)
        try:
            actor = _actor()
            store = _store_with_services(
                StoreService(service_id="my_custom", service_type="custom_service", label="Custom", price=0),
            )

            ok, msg = dispatch_service(actor, store, "custom_service", "my_custom")

            assert ok is True
            assert msg == "custom ok"
            assert results == ["my_custom"]
        finally:
            # Clean up to avoid polluting other tests
            _SERVICE_HANDLERS.pop("custom_service", None)

    def test_registered_handler_overrides_fallback(self):
        """An explicit handler takes priority over generic fallback."""
        call_count = [0]

        def _tracking_handler(actor, store, service, **kwargs):
            call_count[0] += 1
            return True, "tracked"

        register_service_handler("donation", _tracking_handler)
        try:
            actor = _actor(gold=100)
            store = _store_with_services(
                StoreService(service_id="don", service_type="donation", label="Donate", price=10),
            )
            ok, msg = dispatch_service(actor, store, "donation", "don")

            assert ok is True
            assert msg == "tracked"
            assert call_count[0] == 1
            # Gold should NOT be deducted because custom handler didn't do it
            assert actor.stats["gold"] == 100
        finally:
            _SERVICE_HANDLERS.pop("donation", None)


# ── Handler registry shape contract ──────────────────────────────────


class TestHandlerRegistryContract:
    """Freeze the set of built-in handlers that exist."""

    def test_builtin_handlers_present(self):
        assert "room" in _SERVICE_HANDLERS
        assert "identify" in _SERVICE_HANDLERS
        assert "healing" in _SERVICE_HANDLERS
        assert "repair" in _SERVICE_HANDLERS

    def test_all_handlers_are_callable(self):
        for service_type, handler in _SERVICE_HANDLERS.items():
            assert callable(handler), f"Handler for {service_type!r} is not callable"
