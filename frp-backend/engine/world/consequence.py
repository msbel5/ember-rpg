"""
Ember RPG — Consequence Cascading System
Phase 3c
"""
from dataclasses import dataclass, field
import random

from engine.data_loader import get_consequence_rule_specs


@dataclass
class Effect:
    effect_type: str
    target: str
    params: dict
    description: str = ""

    def as_trigger(self) -> dict:
        return {"type": self.effect_type, "target": self.target, **self.params}


@dataclass
class ConsequenceRule:
    rule_id: str
    trigger_type: str
    conditions: dict
    effects: list
    delay_hours: float = 0.0
    probability: float = 1.0
    description: str = ""

    def matches(self, trigger: dict) -> bool:
        if trigger.get("type") != self.trigger_type:
            return False
        for key, value in self.conditions.items():
            if trigger.get(key) != value:
                return False
        return True


@dataclass
class PendingEffect:
    rule_id: str
    effect: dict
    trigger_at_day: int
    trigger_at_hour: float
    original_trigger: dict


class CascadeEngine:
    MAX_CASCADE_DEPTH = 5

    def __init__(self):
        self.rules: list[ConsequenceRule] = []
        self.pending_effects: list[PendingEffect] = []
        self._load_default_rules()

    def _load_default_rules(self):
        self.rules = [
            ConsequenceRule(
                rule_id=str(spec.get("rule_id", "")),
                trigger_type=str(spec.get("trigger_type", "")),
                conditions=dict(spec.get("conditions", {})),
                effects=list(spec.get("effects", [])),
                delay_hours=float(spec.get("delay_hours", 0.0)),
                probability=float(spec.get("probability", 1.0)),
                description=str(spec.get("description", "")),
            )
            for spec in get_consequence_rule_specs()
        ]

    def process_trigger(self, trigger: dict, world_state, depth: int = 0) -> list:
        if depth >= self.MAX_CASCADE_DEPTH:
            return []

        triggered_effects = []

        for rule in self.rules:
            if not rule.matches(trigger):
                continue
            if random.random() > rule.probability:
                continue

            for effect_data in rule.effects:
                effect = Effect(
                    effect_type=effect_data["type"],
                    target=effect_data["target"],
                    params=effect_data.get("params", {}),
                    description=effect_data.get("description", ""),
                )

                if rule.delay_hours == 0:
                    self._apply_effect(effect, trigger, world_state)
                    triggered_effects.append(effect)
                    cascade_trigger = {"type": effect.effect_type, "target": effect.target, **effect.params}
                    self.process_trigger(cascade_trigger, world_state, depth + 1)
                else:
                    t = world_state.current_time
                    total_hours = t.hour + rule.delay_hours
                    self.pending_effects.append(
                        PendingEffect(
                            rule_id=rule.rule_id,
                            effect=effect.__dict__,
                            trigger_at_day=t.day + int(total_hours // 24),
                            trigger_at_hour=total_hours % 24,
                            original_trigger=trigger,
                        )
                    )

        return triggered_effects

    def _apply_effect(self, effect: Effect, trigger: dict, world_state):
        if effect.effect_type == "update_faction_rep":
            faction_id = trigger.get("faction_id", effect.target)
            if faction_id in world_state.factions:
                world_state.factions[faction_id].reputation += effect.params.get("delta", 0)
        elif effect.effect_type == "update_npc_disposition":
            npc_id = trigger.get("npc_id", effect.target)
            npc = world_state.get_npc_state(npc_id)
            npc.disposition += effect.params.get("delta", 0)
        elif effect.effect_type == "set_flag":
            world_state.flags[effect.target] = effect.params.get("value")
        elif effect.effect_type == "alert_guards":
            world_state.flags["guards_alerted"] = True
        world_state.log_event("consequence", effect.description, [effect.target])

    def tick(self, world_state):
        ready = [
            e for e in self.pending_effects
            if (
                e.trigger_at_day < world_state.current_time.day
                or (
                    e.trigger_at_day == world_state.current_time.day
                    and e.trigger_at_hour <= world_state.current_time.hour
                )
            )
        ]
        for pe in ready:
            effect = Effect(**pe.effect)
            self._apply_effect(effect, pe.original_trigger, world_state)
            self.pending_effects.remove(pe)
        return len(ready)

    def to_dict(self) -> dict:
        return {"pending_effects": [pe.__dict__ for pe in self.pending_effects]}

    def from_dict(self, data: dict):
        self.pending_effects = [PendingEffect(**pe) for pe in data.get("pending_effects", [])]
