from __future__ import annotations

from engine.kernel import ActorRecord, tick_effects, tick_syndromes


def effect_events(actor: ActorRecord, current_tick: int) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for effect_event in tick_effects(actor, current_tick):
        events.append(
            {"event_type": effect_event["type"], "summary": f"{actor.identity.display_name} {effect_event['type']}."}
        )
    for syndrome_event in tick_syndromes(actor):
        events.append(
            {"event_type": "syndrome_tick", "summary": f"{actor.identity.display_name} suffered {syndrome_event}."}
        )
    if actor.body_state is not None and not actor.body_state.is_viable():
        actor.alive = False
        actor.stats["hp"] = 0
    return events


__all__ = ["effect_events"]
