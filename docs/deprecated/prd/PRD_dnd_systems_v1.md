# PRD: D&D Core Systems Integration
## Version 1.0 — Missing Systems Pass

Based on D&D 5e Basic Rules analysis. These systems are either missing entirely or partially implemented and need completion.

---

## 1. Full Ability Score System

### Current State
We have 6 abilities (MIG/AGI/END/MND/INS/PRE) in skill_checks.py with modifiers. Basic d20 checks work.

### Missing
- **Proficiency bonus by level** — formula: `(level - 1) // 4 + 2`
- **Skill proficiencies** — characters should have proficiency in specific skills from class/background
- **18 D&D skills mapped to our 6 abilities:**

| Ability | Our Name | D&D Skills |
|---------|----------|------------|
| STR/MIG | Might | Athletics |
| DEX/AGI | Agility | Acrobatics, Sleight of Hand, Stealth |
| CON/END | Endurance | (no skills) |
| INT/MND | Mind | Arcana, History, Investigation, Nature, Religion |
| WIS/INS | Insight | Animal Handling, Insight, Medicine, Perception, Survival |
| CHA/PRE | Presence | Deception, Intimidation, Performance, Persuasion |

### Implementation
- Add `proficiency_bonus` to Character: `(level - 1) // 4 + 2`
- Add `skill_proficiencies: List[str]` to Character
- Check formula: `d20 + ability_modifier + (proficiency_bonus if proficient else 0)`
- Class starting proficiencies:
  - Warrior: Athletics, Intimidation, Perception, Survival (pick 2)
  - Rogue: Acrobatics, Deception, Stealth, Sleight of Hand, Perception, Investigation (pick 4)
  - Mage: Arcana, History, Investigation, Religion, Insight (pick 2)
  - Priest: Medicine, Insight, Persuasion, Religion, History (pick 2)

---

## 2. Passive Checks (CRITICAL — fixes "hidden detail everywhere" problem)

### Current State
NONE. Every check is active (d20 roll). DM fabricates hidden details on every path.

### What D&D Says
- Passive check = `10 + all modifiers` (no dice roll)
- **Passive Perception**: notices hidden threats, traps, ambushes WITHOUT player asking
- **Passive Investigation**: spots clues, inconsistencies WITHOUT player asking
- **Passive Insight**: detects lies, reads mood WITHOUT player asking

### Implementation
- Add `passive_perception`, `passive_investigation`, `passive_insight` to Character
- Formula: `10 + ability_mod + (proficiency_bonus if proficient)`
- **DM prompt must include**: "Player's passive Perception is {X}. Only reveal hidden details if the DC is <= {X}. Most paths are ordinary — do NOT fabricate hidden details unless the location data says something is hidden there."
- When player actively searches: roll d20 check (can find harder things)
- Hidden objects/traps have a DC. Passive check auto-detects if DC <= passive score.

---

## 3. Conditions / Status Effects

### Current State
Basic Condition class in combat.py — only "poisoned" (1d4 damage/turn). No other conditions.

### Missing (D&D 15 conditions)
| Condition | Mechanical Effect |
|-----------|------------------|
| Blinded | Auto-fail sight checks, attacks have disadvantage, attackers have advantage |
| Charmed | Can't attack charmer, charmer has advantage on social checks |
| Deafened | Auto-fail hearing checks |
| Frightened | Disadvantage on checks/attacks while source visible, can't approach source |
| Grappled | Speed 0, ends if grappler incapacitated |
| Incapacitated | Can't take actions or reactions |
| Invisible | Heavily obscured, advantage on attacks, attackers have disadvantage |
| Paralyzed | Incapacitated, can't move/speak, auto-fail STR/DEX saves, hits are crits |
| Petrified | Turned to stone, incapacitated, resistance to all damage |
| Poisoned | Disadvantage on attacks and checks |
| Prone | Crawl only, disadvantage on attacks, melee has advantage / ranged has disadvantage |
| Restrained | Speed 0, disadvantage on attacks/DEX saves, attackers have advantage |
| Stunned | Incapacitated, can't move, auto-fail STR/DEX saves, advantage against |
| Unconscious | Drops items, prone, auto-fail STR/DEX, hits are crits |
| Exhaustion | 6 levels: disadvantage → half speed → disadvantage attacks → half HP → speed 0 → death |

### Implementation
- Expand Condition enum with all 15
- Advantage/disadvantage system: roll 2d20, take higher/lower
- Apply condition effects in combat resolution and skill checks
- Exhaustion tracked on Character, reduced by long rest

---

## 4. Advantage / Disadvantage System

### Current State
Referenced in progression.py but NOT mechanically implemented.

### D&D Rule
- **Advantage**: Roll 2d20, take HIGHER
- **Disadvantage**: Roll 2d20, take LOWER
- Multiple advantages don't stack — still just 2d20
- If you have BOTH advantage and disadvantage, they cancel out (roll normally)

### Implementation
- Add `advantage: bool, disadvantage: bool` parameters to all d20 rolls
- Conditions grant advantage/disadvantage
- Flanking grants advantage
- Attacking unseen target = disadvantage
- Attacking blinded/prone/restrained target = advantage

---

## 5. Social Interaction — NPC Attitudes & Bribe/Persuade/Deceive

### Current State
- `talk to X` works but no attitude tracking
- `bribe` produces generic narration (no mechanic)
- `intimidate` makes a check but no consequences
- No NPC attitude system

### D&D System
NPC attitudes: **Friendly**, **Indifferent**, **Hostile**

| Request Severity | Friendly DC | Indifferent DC | Hostile DC |
|-----------------|-------------|----------------|------------|
| No risk/cost | No check | DC 10 | DC 20 |
| Minor risk/cost | DC 10 | DC 15 | DC 25 |
| Significant sacrifice | DC 15 | DC 20 | DC 30 (impossible) |

**Attitude shifts:**
- Bribe/gift → shift one step friendlier (if value >= threshold)
- Successful Persuasion → temporary shift
- Attack/crime → shift to Hostile (permanent unless atoned)
- Repeated positive interactions → permanent shift

### Implementation
- Add `attitude: str` to NPC entity data (friendly/indifferent/hostile)
- Bribe = Persuasion check with DC modified by gift value
- Intimidate = contested check (attacker PRE vs defender INS)
- Deceive = Deception check vs target's Passive Insight
- After crime (attack, steal), all witnesses shift to Hostile
- Guards in the area are alerted

---

## 6. Conversation Target System (Radio Button)

### Current State
Ambiguous — "talk merchant" works but free text could be to DM, self, or NPC.

### Design
- Default speech target: **DM** (ask questions, request actions)
- `talk to <NPC>` switches target to that NPC
- `think` or `to self` = internal monologue → DM may trigger skill check
  - "What do I know about this?" → History/Arcana/Religion check
  - DC based on obscurity: common knowledge DC 5, specialized DC 15, secret DC 25
  - Crit success: deep knowledge. Near miss: vague memory. Fail: nothing.
- **Eavesdroppers**: NPCs within 2 tiles of a conversation can hear it
  - If player discusses crime near a guard → guard reacts
  - If player discusses plans near a spy → information leaks
- When in conversation with NPC, responses default to that NPC until player leaves range or switches

### Parser Changes
- Add `THINK` intent: "think about", "recall", "what do I know", "to self", "düşün", "hatırla"
- Add `ADDRESS` intent: "talk to <name>", "say to <name>"
- Free text while in conversation → routed to current conversation target

---

## 7. Short Rest vs Long Rest

### Current State
Only one "rest" = 8 hours, full recovery.

### D&D System
| Rest Type | Duration | Recovery |
|-----------|----------|----------|
| Short Rest | 1 hour | Spend Hit Dice to heal (d10 warrior, d8 rogue, d6 mage, d8 priest) |
| Long Rest | 8 hours | Full HP, regain half spent Hit Dice, -1 exhaustion |

### Implementation
- `rest` or `short rest` = 1 hour, spend Hit Dice
- `long rest` or `sleep` or `camp` = 8 hours, full recovery
- Hit Dice pool: level * class_hit_die, tracked per session
- Long rest restores half of max Hit Dice (rounded down, minimum 1)
- Can't long rest more than once per 24 game-hours

---

## 8. Alignment System

### Current State
NPCs have `faction_alignment` but it's faction-based, not personal.

### D&D 9 Alignments
| | Lawful | Neutral | Chaotic |
|---|--------|---------|---------|
| **Good** | LG: Crusader | NG: Benefactor | CG: Rebel |
| **Neutral** | LN: Judge | TN: Undecided | CN: Free Spirit |
| **Evil** | LE: Dominator | NE: Malefactor | CE: Destroyer |

### Implementation
- Add `alignment: str` to Character and NPC entities (e.g., "LG", "CN", "NE")
- Player chooses at character creation
- NPC alignment affects:
  - Willingness to help (Evil NPCs demand payment, Good NPCs offer freely)
  - Reaction to crimes (Lawful NPCs report, Chaotic NPCs ignore minor crimes)
  - Quest availability (Evil quests only from Evil NPCs)
- Player alignment shifts based on actions (kill innocent → shift toward Evil)

---

## 9. Initiative & Combat Action Economy

### Current State
Turn-based combat exists but no initiative roll. No bonus actions or reactions.

### D&D System
- Initiative: d20 + DEX modifier (determines turn order)
- Per turn: 1 Action + 1 Bonus Action + 1 Reaction + Movement
- Opportunity Attack: reaction when enemy leaves your reach
- Bonus actions: off-hand attack (dual wield), certain spells

### Implementation
- Roll initiative at combat start for all combatants
- Sort by initiative (highest first, DEX breaks ties)
- Add bonus action slot (rogue dual wield, priest healing word)
- Opportunity attacks when fleeing without Disengage action
- Disengage action: no opportunity attacks this turn (costs Action)

---

## 10. Death Saving Throws

### Current State
HP hits 0 = dead. No death saves.

### D&D System
- At 0 HP: unconscious, not dead
- Each turn: death saving throw (d20, DC 10)
  - 10+: success. <10: failure
  - Nat 20: regain 1 HP. Nat 1: 2 failures
  - 3 successes: stabilized (unconscious but not dying)
  - 3 failures: dead
- Any healing while at 0 HP: conscious again with that HP
- Any damage while at 0 HP: 1 death save failure (crit = 2)

### Implementation
- At 0 HP: set condition UNCONSCIOUS, start death saves
- Track `death_save_successes` and `death_save_failures` on Character
- Healing at 0 HP: clear death saves, regain consciousness
- Stabilized: no more death saves until damaged again

---

## Sprint Plan

### Sprint 1: Foundations (proficiency, passive checks, advantage)
- Proficiency bonus on Character
- Skill proficiencies per class
- Passive Perception/Investigation/Insight
- Advantage/disadvantage on d20 rolls
- DM prompt: "Only reveal hidden details if DC <= passive Perception"

### Sprint 2: Conditions & Rest
- 15 conditions enum with mechanical effects
- Advantage/disadvantage from conditions in combat
- Exhaustion 6-level system
- Short rest (1 hour, hit dice) vs Long rest (8 hours, full)

### Sprint 3: Social & Conversation
- NPC attitudes (Friendly/Indifferent/Hostile) with DC table
- Bribe/Persuade/Intimidate/Deceive proper mechanics
- Conversation target system (DM/NPC/Self)
- THINK intent for knowledge checks
- Eavesdropper mechanic (nearby NPCs hear conversations)

### Sprint 4: Combat Polish
- Initiative rolls, turn order
- Death saving throws
- Opportunity attacks
- Disengage action
- Alignment on characters and NPCs

### Sprint 5: Integration & Test
- Wire all new systems into GameEngine
- Update save/load for new fields
- Update terminal client
- 100-turn chaos play-test
- Fix everything found
