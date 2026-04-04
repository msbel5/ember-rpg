"""Player initialization for campaign context.

Returns player-state fields that get set on CampaignContext directly.
No separate session object is created.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from engine.api.runtime_constants import DEFAULT_PLAYER_CLASS, LOCATION_STOCK_BASELINE, OPENING_SCENES, STARTER_KITS
from engine.world.action_points import ActionPointTracker
from engine.world.body_parts import BodyPartTracker
from engine.world.caravans import CaravanManager
from engine.world.quest_timeout import QuestTracker
from engine.world.schedules import GameTime as LivingGameTime
from engine.world.spatial_index import SpatialIndex
from engine.world.viewport import Viewport
from engine.kernel.actor_records import create_player_actor
from engine.kernel.creation import (
    CLASS_DEFAULT_SKILLS,
    CLASS_SKILL_COUNTS,
    CLASS_SKILL_OPTIONS,
    recommended_alignment_from_axes,
    recommended_skills_for_class,
)
from engine.kernel.scene_types import SceneContext, SceneType
from engine.data_loader import (
    get_class,
    get_class_default_hp,
    get_class_default_spell_points,
    get_class_default_stats,
    get_creation_unknown_class_fallback,
)
from engine.world.economy import LocationStock
from engine.world.history import HistorySeed
from engine.world.naming import NameGenerator


@dataclass
class PlayerInitState:
    """Data returned by create_player_state — absorbed into CampaignContext."""
    player: Any
    dm_context: SceneContext
    body_tracker: Optional[Any] = None
    location_stock: Optional[Any] = None
    ap_tracker: Optional[Any] = None
    caravan_manager: Optional[Any] = None
    game_time: Optional[Any] = None
    spatial_index: Optional[Any] = None
    viewport: Optional[Any] = None
    quest_tracker: Optional[Any] = None
    history_seed: Optional[Any] = None
    name_gen: Optional[Any] = None


def create_player_state(
    player_name: str,
    player_class: str = "warrior",
    location: str | None = None,
    *,
    alignment: str | None = None,
    skill_proficiencies: list[str] | None = None,
    stats: dict[str, int] | None = None,
    creation_answers: list | None = None,
    creation_profile: dict | None = None,
) -> PlayerInitState:
    """Create player actor and subsystems. Returns PlayerInitState for context absorption."""
    unknown_class_fallback = get_creation_unknown_class_fallback()
    player_class = str(player_class or DEFAULT_PLAYER_CLASS).lower()
    unknown_class = not get_class(player_class)
    class_stats_template = {} if unknown_class else get_class_default_stats(player_class)
    if unknown_class:
        player_class = str(unknown_class_fallback.get("class_id") or DEFAULT_PLAYER_CLASS).lower()
        class_stats_template = get_class_default_stats(player_class)
    assigned_stats = dict(stats or {})
    if assigned_stats:
        for key in ("MIG", "AGI", "END", "MND", "INS", "PRE"):
            assigned_stats.setdefault(key, 10)
    else:
        assigned_stats = dict(class_stats_template)
    hp = int(unknown_class_fallback.get("hp", 0)) if unknown_class else get_class_default_hp(player_class)
    sp = get_class_default_spell_points(player_class)

    creation_profile = dict(creation_profile or {})
    recommended_axes = dict(creation_profile.get("alignment_axes") or {})
    effective_alignment = alignment or recommended_alignment_from_axes(recommended_axes) if recommended_axes else (alignment or "TN")
    default_skills = recommended_skills_for_class({"skill_weights": creation_profile.get("skill_weights", {})}, player_class)
    selected_skills = list(skill_proficiencies or default_skills or CLASS_DEFAULT_SKILLS.get(player_class, []))
    allowed_skills = set(CLASS_SKILL_OPTIONS.get(player_class, []))
    selected_skills = [skill for skill in selected_skills if skill in allowed_skills][: CLASS_SKILL_COUNTS.get(player_class, 2)]
    if len(selected_skills) < CLASS_SKILL_COUNTS.get(player_class, 2):
        for fallback in CLASS_DEFAULT_SKILLS.get(player_class, []):
            if fallback in allowed_skills and fallback not in selected_skills:
                selected_skills.append(fallback)
            if len(selected_skills) >= CLASS_SKILL_COUNTS.get(player_class, 2):
                break

    player = create_player_actor(
        name=player_name,
        class_name=player_class,
        stats=assigned_stats,
        level=1,
        skills={skill: 0 for skill in selected_skills},
    )
    player.stats["hp"] = hp
    player.stats["max_hp"] = hp
    player.raw_payload.update({
        "hp": hp,
        "max_hp": hp,
        "spell_points": sp,
        "max_spell_points": sp,
        "xp": 0,
        "classes": {player_class: 1},
        "skill_proficiencies": selected_skills,
        "alignment": effective_alignment or "TN",
        "creation_answers": list(creation_answers or []),
        "creation_profile": creation_profile,
        "use_death_saves": True,
    })
    if not alignment and recommended_axes:
        lc = recommended_axes.get("law_chaos", 0)
        ge = recommended_axes.get("good_evil", 0)
        first = "L" if lc > 0 else ("C" if lc < 0 else "T")
        second = "G" if ge > 0 else ("E" if ge < 0 else "N")
        player.raw_payload["alignment"] = first + second
        player.raw_payload["alignment_axes"] = dict(recommended_axes)

    loc = OPENING_SCENES[0][0] if location is None else location
    dm_context = SceneContext(scene_type=SceneType.EXPLORATION, location=loc, party=[player])

    result = PlayerInitState(player=player, dm_context=dm_context)

    seed = hash(str(id(player))) % 1000000
    result.history_seed = HistorySeed().generate(seed=seed)
    result.name_gen = NameGenerator(seed=seed)

    result.body_tracker = BodyPartTracker()
    hp_scale = max(0.1, player.max_hp / 20.0)
    for part in result.body_tracker.max_hp:
        result.body_tracker.max_hp[part] = max(1, int(result.body_tracker.max_hp[part] * hp_scale))
        result.body_tracker.current_hp[part] = result.body_tracker.max_hp[part]

    result.location_stock = LocationStock(location_id=loc.lower().replace(" ", "_"), baseline=LOCATION_STOCK_BASELINE)
    result.ap_tracker = ActionPointTracker(max_ap=4)
    result.caravan_manager = CaravanManager()
    result.game_time = LivingGameTime()
    result.spatial_index = SpatialIndex()
    result.viewport = Viewport()
    result.quest_tracker = QuestTracker()

    kit = STARTER_KITS.get(player_class.lower(), STARTER_KITS[DEFAULT_PLAYER_CLASS])
    for item_template in kit:
        item = dict(item_template)
        slot = item.get("slot")
        if slot and not player.equipment.slots.get(slot):
            from engine.kernel.actor_items import item_stack_from_legacy_payload

            equipped_item = item_stack_from_legacy_payload(item)
            player.equipment.add_item(slot, equipped_item)
            if slot == "armor" and result.ap_tracker:
                material = item.get("material", "none")
                armor_weight_map = {
                    "cloth": "cloth",
                    "leather": "leather",
                    "iron": "chain_mail",
                    "steel": "plate_armor",
                }
                result.ap_tracker.set_armor(armor_weight_map.get(material, "none"))
        else:
            from engine.kernel.actor_items import item_stack_from_legacy_payload
            try:
                stack = item_stack_from_legacy_payload(item)
                player.inventory.append(stack)
            except Exception:
                pass

    player.stats.setdefault("hp", player.stats.get("max_hp", 10))
    player.stats.setdefault("max_hp", player.stats.get("hp", 10))
    return result


__all__ = ["create_player_state", "PlayerInitState"]
