"""
Ember RPG — Consequence Cascading System
Phase 3c
"""
from dataclasses import dataclass, field
import random


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
                rule_id="merchant_killed_price_rise",
                trigger_type="npc_killed",
                conditions={"npc_role": "merchant"},
                effects=[{"type": "update_location_price", "target": "current", "params": {"delta_pct": 30}, "description": "Merchant killed — local prices rise 30%"}],
                delay_hours=0,
                probability=1.0,
                description="Killing a merchant raises local prices",
            ),
            ConsequenceRule(
                rule_id="merchant_killed_reputation",
                trigger_type="npc_killed",
                conditions={"npc_role": "merchant"},
                effects=[{"type": "update_faction_rep", "target": "merchants_guild", "params": {"delta": -20}, "description": "Merchants guild reputation -20"}],
                delay_hours=0,
                probability=1.0,
            ),
            ConsequenceRule(
                rule_id="witnessed_kill_guards_alert",
                trigger_type="npc_killed",
                conditions={"witnessed": True},
                effects=[{"type": "alert_guards", "target": "current_location", "params": {}, "description": "Guards alerted to the killing"}],
                delay_hours=1,
                probability=0.8,
            ),
            ConsequenceRule(
                rule_id="witnessed_kill_bounty",
                trigger_type="npc_killed",
                conditions={"witnessed": True},
                effects=[{"type": "set_flag", "target": "player_has_bounty", "params": {"value": True}, "description": "Bounty placed on player"}],
                delay_hours=24,
                probability=0.9,
            ),
            ConsequenceRule(
                rule_id="quest_giver_killed",
                trigger_type="npc_killed",
                conditions={"npc_role": "quest_giver"},
                effects=[{"type": "fail_related_quests", "target": "npc_quests", "params": {}, "description": "Quest giver dead — related quests fail"}],
                delay_hours=0,
                probability=1.0,
            ),
            ConsequenceRule(
                rule_id="helped_npc_disposition",
                trigger_type="npc_helped",
                conditions={},
                effects=[{"type": "update_npc_disposition", "target": "target_npc", "params": {"delta": 15}, "description": "NPC disposition +15"}],
                delay_hours=0,
                probability=1.0,
            ),
            ConsequenceRule(
                rule_id="helped_merchant_discount",
                trigger_type="npc_helped",
                conditions={"npc_role": "merchant"},
                effects=[{"type": "set_npc_flag", "target": "target_npc", "params": {"flag": "discount_10pct", "value": True}, "description": "Merchant offers 10% discount"}],
                delay_hours=0,
                probability=1.0,
            ),
            ConsequenceRule(
                rule_id="steal_detected_guards",
                trigger_type="item_stolen",
                conditions={"detected": True},
                effects=[{"type": "alert_guards", "target": "current_location", "params": {}, "description": "Theft detected — guards alerted"}],
                delay_hours=0,
                probability=1.0,
            ),
            ConsequenceRule(
                rule_id="quest_completed_faction_rep",
                trigger_type="quest_completed",
                conditions={"reward_type": "faction"},
                effects=[{"type": "update_faction_rep", "target": "quest_faction", "params": {"delta": 15}, "description": "Faction reputation +15 for quest completion"}],
                delay_hours=0,
                probability=1.0,
            ),
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
