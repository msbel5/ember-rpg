# PRD: Consequence Cascading System
# Phase 3c — Makes the World Feel Alive
# Priority: HIGH — BG3's best feature, AI Dungeon's biggest weakness

## 1. Overview
Every player action ripples through the world. Kill a merchant → prices rise → town reputation drops → guards become hostile → new quest appears to restore order. This is the system that makes Ember RPG feel alive.

## 2. Architecture

```
Player Action
    ↓
Action Classifier (what type of action?)
    ↓
Direct Consequence (immediate effect)
    ↓
Cascade Engine (check all trigger rules)
    ↓
World State Update
    ↓
NPC Memory Update
    ↓
Quest System Check (new quests? quest failures?)
    ↓
AI Context Refresh
```

## 3. Consequence Rules

### Rule Format
```python
class ConsequenceRule:
    trigger: str          # "npc_killed", "quest_completed", "item_stolen"
    conditions: dict      # {"npc_role": "merchant", "faction": "town_guild"}
    effects: list[Effect] # list of world state changes
    delay: int = 0        # game hours before effect triggers
    probability: float = 1.0  # chance of triggering
```

### Core Rules

#### Violence Consequences
| Trigger | Condition | Effect | Delay |
|---------|-----------|--------|-------|
| Kill NPC | role=merchant | Prices +30% in location | 0 |
| Kill NPC | role=merchant | Faction reputation -20 | 0 |
| Kill NPC | witnessed=True | Guards alerted | 1 hour |
| Kill NPC | witnessed=True | Bounty placed on player | 24 hours |
| Kill NPC | role=quest_giver | Related quests fail | 0 |
| Attack NPC | any | NPC disposition -50 | 0 |
| Attack NPC | faction=guards | All guards hostile | 0 |

#### Social Consequences
| Trigger | Condition | Effect | Delay |
|---------|-----------|--------|-------|
| Help NPC | any | NPC disposition +15 | 0 |
| Help NPC | role=merchant | Discount 10% | 0 |
| Lie to NPC | detected=True | NPC disposition -20, trust broken | 0 |
| Steal from NPC | detected=True | Guards alerted, reputation -15 | 0 |
| Steal from NPC | detected=False | Item obtained, no immediate effect | 0 |
| Bribe NPC | any | NPC disposition +10, gold lost | 0 |

#### Quest Consequences
| Trigger | Condition | Effect | Delay |
|---------|-----------|--------|-------|
| Quest complete | reward_type=faction | Faction reputation +15 | 0 |
| Quest complete | has_choice | World flag set based on choice | 0 |
| Quest fail | has_penalty | Reputation -10 | 0 |
| Quest ignore | timeout=True | NPC disappointment, new consequence | 7 days |

#### Economic Consequences
| Trigger | Condition | Effect | Delay |
|---------|-----------|--------|-------|
| Buy all stock | item_type=weapons | Price +20% next restock | 24 hours |
| Sell rare item | to=merchant | Merchant sells it to others | 48 hours |
| Flood market | same_item > 5 | Price crash for that item | 0 |

## 4. Cascade Engine

```python
class CascadeEngine:
    rules: list[ConsequenceRule]
    pending_effects: list[PendingEffect]  # delayed effects

    def process_action(self, action, world_state):
        triggered = []

        for rule in self.rules:
            if rule.matches(action):
                if rule.delay == 0:
                    effects = rule.apply(world_state)
                    triggered.extend(effects)
                else:
                    self.pending_effects.append(
                        PendingEffect(rule, trigger_time=world_state.time + rule.delay)
                    )

        # Check if any effects trigger further cascades
        for effect in triggered:
            self.process_action(effect.as_action(), world_state)  # recursive!

        return triggered

    def tick(self, world_state):
        """Called on time passage — check delayed effects"""
        ready = [e for e in self.pending_effects if e.trigger_time <= world_state.time]
        for effect in ready:
            effect.apply(world_state)
            self.pending_effects.remove(effect)
```

## 5. Acceptance Criteria

### AC-1: Direct Consequences
- [ ] Kill merchant → prices rise immediately
- [ ] Help NPC → disposition increases
- [ ] Steal detected → guards alerted

### AC-2: Delayed Consequences
- [ ] Witnessed kill → bounty after 24 game hours
- [ ] Ignored quest → NPC disappointment after 7 days
- [ ] Time tick processes all pending effects

### AC-3: Cascade Chains
- [ ] Kill merchant → prices rise → poor NPCs complain → new quest to find new merchant
- [ ] At least 3-deep cascade chain works correctly
- [ ] No infinite loops (max cascade depth = 5)

### AC-4: World State Integration
- [ ] All consequences update world state ledger
- [ ] AI DM narrative reflects consequences
- [ ] NPCs reference consequences in dialogue

### AC-5: Save/Load
- [ ] Pending delayed effects saved
- [ ] Consequence history preserved
- [ ] Rules state preserved

### AC-6: API Endpoints
- [ ] GET /game/session/{id}/consequences — active consequences
- [ ] GET /game/session/{id}/pending — delayed effects queue

## 6. Test Scenarios
1. Kill merchant → verify price increase + reputation drop
2. Wait 24 game hours after witnessed kill → verify bounty appears
3. Complete quest → verify faction reputation + world flag changes
4. Chain: help merchant → get discount → buy cheap → sell expensive elsewhere
5. Save/load with pending delayed effects → verify they still trigger
6. Max cascade depth → verify no infinite loop
