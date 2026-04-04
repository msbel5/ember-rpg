"""Standalone session creation extracted from GameEngine.new_session()."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.api.session.core import GameSession
from engine.api.runtime_constants import CLASS_ALIASES, DEFAULT_PLAYER_CLASS, LOCATION_STOCK_BASELINE, OPENING_SCENES, STARTER_KITS
from engine.kernel.actor_records import create_player_actor
from engine.kernel.creation import (
    CLASS_DEFAULT_SKILLS,
    CLASS_SKILL_COUNTS,
    CLASS_SKILL_OPTIONS,
    recommended_alignment_from_axes,
    recommended_skills_for_class,
)
from engine.kernel.scene_types import DMContext, SceneType
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


def create_game_session(
    player_name: str,
    player_class: str = "warrior",
    location: str | None = None,
    *,
    alignment: str | None = None,
    skill_proficiencies: list[str] | None = None,
    stats: dict[str, int] | None = None,
    creation_answers: list | None = None,
    creation_profile: dict | None = None,
) -> GameSession:
    """Create a fully initialized GameSession with player actor, stats, skills, and equipment."""
    unknown_class_fallback = get_creation_unknown_class_fallback()
    requested_class = str(player_class or DEFAULT_PLAYER_CLASS).lower()
    player_class = CLASS_ALIASES.get(requested_class, requested_class)
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
    # Carry over legacy fields in raw_payload
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
        # Derive alignment code from axes
        lc = recommended_axes.get("law_chaos", 0)
        ge = recommended_axes.get("good_evil", 0)
        first = "L" if lc > 0 else ("C" if lc < 0 else "T")
        second = "G" if ge > 0 else ("E" if ge < 0 else "N")
        player.raw_payload["alignment"] = first + second
        player.raw_payload["alignment_axes"] = dict(recommended_axes)

    loc = OPENING_SCENES[0][0] if location is None else location
    dm_context = DMContext(scene_type=SceneType.EXPLORATION, location=loc, party=[player])
    session = GameSession(player=player, dm_context=dm_context)

    seed = hash(session.session_id) % 1000000
    session.history_seed = HistorySeed().generate(seed=seed)
    session.name_gen = NameGenerator(seed=seed)

    hp_scale = player.max_hp / 20.0
    for part in session.body_tracker.max_hp:
        session.body_tracker.max_hp[part] = max(1, int(session.body_tracker.max_hp[part] * hp_scale))
        session.body_tracker.current_hp[part] = session.body_tracker.max_hp[part]

    session.location_stock = LocationStock(location_id=loc.lower().replace(" ", "_"), baseline=LOCATION_STOCK_BASELINE)

    kit = STARTER_KITS.get(player_class.lower(), STARTER_KITS[DEFAULT_PLAYER_CLASS])
    for item_template in kit:
        item = dict(item_template)
        slot = item.get("slot")
        if slot and session.equipment.get(slot) is None:
            session.set_equipment_slot(slot, item)
            if slot == "armor" and session.ap_tracker:
                material = item.get("material", "none")
                armor_weight_map = {
                    "cloth": "cloth",
                    "leather": "leather",
                    "iron": "chain_mail",
                    "steel": "plate_armor",
                }
                session.ap_tracker.set_armor(armor_weight_map.get(material, "none"))
        else:
            session.add_item(item)

    session.ensure_consistency()
    return session
