# FRP AI Game — Game Design Document (GDD)
**Version:** 0.1 (Initial Draft)  
**Date:** 2026-03-22  
**Author:** Alcyone  

---

## 1. Vision

**A 2D fantasy role-playing game powered by AI agents** where:
- The **AI Dungeon Master** creates dynamic stories, encounters, and challenges
- **AI NPCs** have memory, personality, and consistent behavior
- **AI systems** generate maps, campaigns, and quests on the fly
- Players experience a **living, reactive world** that adapts to their choices

**Not a D&D clone.** We build our own rule system from scratch — simpler, clearer, AI-friendly.

**Target platforms:** Steam (PC), Web, Mobile (future)

---

## 2. Core Pillars

### 2.1 AI-Driven Narrative
- **DM Agent**: LLM-powered storyteller, encounter designer, rule arbiter
- **Dynamic campaigns**: No pre-scripted paths, AI generates story beats
- **Player agency**: Choices matter, AI adapts

### 2.2 Intelligent NPCs
- **Memory system**: NPCs remember past interactions
- **Personality traits**: Each NPC has consistent behavior
- **Dialogue**: Natural language, context-aware

### 2.3 Strategic Combat
- **Turn-based**: Tactical, grid-optional
- **Action economy**: Move + Action + Bonus (simplified)
- **Environmental factors**: Cover, terrain, line of sight

### 2.4 Living World
- **Procedural maps**: 2D tile-based dungeons, towns, wilderness
- **Quest chains**: AI-generated objectives with consequences
- **Persistent state**: World evolves based on player actions

---

## 3. Rule System: "Ember RPG"

### 3.1 Core Mechanics

**Dice:** d20 + d6 + d10 (no d4/d8/d12 to keep it simple)

**Core resolution:**
```
d20 + Stat Modifier + Skill ≥ Target Number → Success
```

**Critical success:** Natural 20  
**Critical failure:** Natural 1

### 3.2 Attributes (6 Core Stats)

1. **Might (MIG)** — Physical power, melee damage
2. **Agility (AGI)** — Speed, reflexes, ranged attacks
3. **Endurance (END)** — HP, stamina, resistance
4. **Mind (MND)** — Magic power, spell slots
5. **Insight (INS)** — Perception, intuition, initiative
6. **Presence (PRE)** — Charisma, leadership, persuasion

**Starting values:** 8-14 (rolled or point-buy)  
**Modifier:** `(Stat - 10) / 2` (rounded down)

### 3.3 Health & Damage

**HP = 10 + (END × 2) + Class Bonus**

**Damage types:**
- Physical (slashing, piercing, bludgeoning)
- Elemental (fire, cold, lightning)
- Arcane (pure magic)
- Necrotic (death energy)

**Death:** 0 HP → Unconscious, -10 HP → Dead (or Death Saves)

### 3.4 Skills (12 Core)

**Physical:** Athletics, Stealth, Survival  
**Combat:** Melee, Ranged, Defense  
**Mental:** Arcana, Lore, Perception  
**Social:** Persuasion, Deception, Intimidation

**Proficiency:** +2 bonus at level 1, scales to +6 at level 20

### 3.5 Classes (4 Archetypes)

#### Warrior
- **HP:** High (END × 3)
- **Key stats:** MIG, END
- **Features:** 
  - Extra attack at level 5
  - Armor mastery (+2 AC)
  - Second wind (heal 1/rest)

#### Rogue
- **HP:** Medium (END × 2)
- **Key stats:** AGI, INS
- **Features:**
  - Sneak attack (+2d6 damage)
  - Evasion (dodge AoE)
  - Cunning action (bonus dash/hide)

#### Mage
- **HP:** Low (END × 1.5)
- **Key stats:** MND, INS
- **Features:**
  - Spellcasting (3 spell slots at L1, scales to 9 at L20)
  - Spell library (learn 2 per level)
  - Arcane recovery (1/day regain slots)

#### Priest
- **HP:** Medium (END × 2)
- **Key stats:** MND, PRE
- **Features:**
  - Divine spells (healing, buffs)
  - Turn undead
  - Channel divinity (1/rest)

### 3.6 Magic System

**Spell Slots:** 3 at L1 → 9 at L20  
**Spell Levels:** 1 (cantrip-like) to 5 (max power)

**Cost:** Cast any spell, consume 1 slot (no spell-level slots, simplified)

**Spell Schools:**
- Evocation (damage)
- Abjuration (defense)
- Conjuration (summon)
- Restoration (healing)
- Transmutation (buff/debuff)
- Illusion (tricks)

**Spell power:** `1d6 + MND modifier + spell level`

### 3.7 Combat Rules

**Turn order:** Initiative = d20 + INS modifier

**Action economy (per turn):**
- **Move:** Up to speed (6 tiles default)
- **Action:** Attack, cast spell, use item, help
- **Bonus action:** Class features, quick actions

**Attack roll:**
```
d20 + (MIG or AGI) + Proficiency ≥ Target AC
```

**Damage roll:**
```
Weapon die + Stat modifier
```

**Armor Class (AC):**
```
10 + AGI modifier + Armor bonus
```

**Armor types:**
- Light: +2 AC
- Medium: +4 AC (max AGI +2)
- Heavy: +6 AC (no AGI bonus)

### 3.8 Leveling & XP

**XP to level up:**
```
Level 1→2: 100 XP
Level 2→3: 200 XP
Level N→N+1: N × 100 XP
```

**Per level:**
- +1 to any stat (max 20)
- +1d6 HP (+ END mod)
- New skill proficiency or spell
- Class feature (every 2-3 levels)

---

## 4. AI Systems

### 4.1 DM Agent

**Role:** Storyteller, encounter designer, rule arbiter

**Capabilities:**
- Generate story hooks
- Describe scenes (text-based, 2D tile refs)
- Create encounters (combat, puzzles, social)
- Adjudicate rule edge cases
- Track campaign state

**Model:** Qwen3:7b (local) or Claude Sonnet (API)

**Memory:**
- Campaign summary (last 10 sessions)
- Active quests
- NPC relationships
- World state (destroyed villages, defeated bosses, etc.)

**Prompt structure:**
```
System: You are the DM for Ember RPG. You create dynamic stories...
Campaign context: [summary]
Current scene: [description]
Player action: [input]
Generate: next scene + encounter + consequences
```

### 4.2 NPC Agent

**Role:** Consistent characters with memory and personality

**Capabilities:**
- Remember past interactions (vector DB or JSON log)
- Personality traits (brave/cowardly, honest/deceptive, etc.)
- Dialogue generation (context-aware)
- Relationship tracking (friendly/neutral/hostile)

**Model:** Qwen3:1.7b (fast, local) or GPT-4o-mini

**Memory per NPC:**
```json
{
  "name": "Elara the Blacksmith",
  "personality": ["gruff", "loyal", "secretive"],
  "memory": [
    "Player saved her shop from bandits (session 3)",
    "Owes player a favor"
  ],
  "relationship": 75,
  "last_seen": "session 5"
}
```

**Dialogue prompt:**
```
Character: Elara (gruff blacksmith, owes player a favor)
Player says: "Can you forge me a magic sword?"
Context: Player saved her shop
Generate: NPC response (in character)
```

### 4.3 Map Generator

**Role:** Procedural 2D tile-based maps

**Types:**
- Dungeons (rooms + corridors)
- Towns (buildings + streets)
- Wilderness (forests, mountains, rivers)

**Algorithm:**
- BSP (Binary Space Partitioning) for dungeons
- Voronoi/noise for wilderness
- Template-based for towns

**Output:**
```json
{
  "size": [40, 40],
  "tiles": [
    {"x": 0, "y": 0, "type": "floor"},
    {"x": 1, "y": 0, "type": "wall"},
    ...
  ],
  "entities": [
    {"x": 5, "y": 10, "type": "chest", "loot": ["gold:50", "potion:healing"]}
  ]
}
```

### 4.4 Campaign Generator

**Role:** Quest chains, world lore, story arcs

**Capabilities:**
- Main quest (5-10 sessions)
- Side quests (1-3 sessions each)
- Random encounters
- World events (war, plague, festival)

**Structure:**
```json
{
  "campaign": "The Shadow of Morvain",
  "main_quest": [
    {"id": 1, "title": "The Missing Caravan", "objective": "Find the lost merchants"},
    {"id": 2, "title": "Bandits of the Black Forest", "objective": "Clear the bandit camp"}
  ],
  "side_quests": [
    {"title": "Blacksmith's Secret", "giver": "Elara", "reward": "Magic weapon"}
  ],
  "world_state": {
    "bandit_threat_level": 8,
    "kingdom_stability": 5
  }
}
```

---

## 5. Game Loop

### 5.1 Session Flow

1. **DM Agent**: Describe scene
2. **Player**: Declare action (move/attack/talk/cast/etc.)
3. **DM Agent**: Resolve action (dice rolls, consequences)
4. **NPC Agent**: React (if NPCs present)
5. **Update state**: HP, inventory, quest progress
6. **Repeat**

### 5.2 Combat Flow

1. **Initiative:** Roll d20 + INS
2. **Turn order:** Highest to lowest
3. **Player turn:**
   - Move (up to speed)
   - Action (attack/spell/item)
   - Bonus action (if available)
4. **Enemy turn:** AI decides action (attack/flee/cast/etc.)
5. **End conditions:** All enemies dead OR all players dead/fled

### 5.3 Exploration Flow

1. **DM generates map** (if entering new area)
2. **Player moves** on tile grid
3. **DM rolls random encounter** (10% per move)
4. **Player interacts** with objects/NPCs/environment
5. **DM updates quest progress**

---

## 6. Multiplayer (Future)

**Co-op party:**
- 2-4 players
- AI fills missing roles (if 2 players, AI adds 2 NPCs)
- Shared XP, individual loot

**PvP arena:**
- Turn-based combat
- AI referee (enforces rules)

---

## 7. Technical Architecture (Phase 2)

### 7.1 Backend Components

```
frp-game/
├── engine/
│   ├── rules.py          # Core mechanics (dice, stats, combat)
│   ├── combat.py         # Turn-based combat engine
│   ├── character.py      # Character sheet, leveling
│   └── world.py          # World state, quests
│
├── ai/
│   ├── dm_agent.py       # DM LLM integration
│   ├── npc_agent.py      # NPC dialogue + memory
│   ├── map_gen.py        # Procedural map generator
│   └── campaign_gen.py   # Quest + story generator
│
├── data/
│   ├── spells.json       # Spell library
│   ├── items.json        # Weapons, armor, potions
│   ├── monsters.json     # Bestiary
│   └── campaigns/        # Campaign templates
│
├── server/
│   ├── api.py            # REST/WebSocket API
│   └── session.py        # Game session manager
│
└── tests/
    ├── test_combat.py
    ├── test_dm.py
    └── test_map_gen.py
```

### 7.2 Data Flow

```
Player input → API → DM Agent → Rules Engine → State Update → Response
                         ↓
                    NPC Agent (if dialogue)
                         ↓
                    Map Gen (if new area)
```

---

## 8. Phase 1 Deliverables

✅ **This GDD**

Next:
- Spell list (50 spells)
- Item database (weapons, armor, potions)
- Monster bestiary (20 creatures)
- Sample campaign (intro quest chain)

---

## 9. Phase 2 MVP Scope

**Must-have:**
- DM agent (story generation)
- Combat engine (turn-based)
- Character creation + leveling
- NPC dialogue (basic memory)
- Map generator (dungeon only)

**Nice-to-have:**
- Campaign generator
- Item crafting
- Multiplayer

**Out of scope (later):**
- Graphics/sprites (text-based MVP)
- Voice acting
- Achievements

---

## 10. Success Metrics

**Phase 2 MVP:**
- [ ] Create character (all 4 classes)
- [ ] Complete 1 combat encounter (3 enemies)
- [ ] Talk to NPC (remembers previous interaction)
- [ ] Generate 1 dungeon map (5 rooms)
- [ ] DM generates story scene based on player action

**Full game:**
- 10+ hour campaign
- 100+ items/spells
- 50+ monster types
- Player retention: 60%+ finish campaign

---

## 11. Risks & Mitigations

**Risk 1:** AI generates inconsistent story  
**Mitigation:** Structured prompts, memory system, rule constraints

**Risk 2:** Combat balance (too easy/hard)  
**Mitigation:** Playtesting, tunable difficulty

**Risk 3:** LLM cost (API usage)  
**Mitigation:** Use local Qwen3 for most calls, Claude only for critical decisions

**Risk 4:** Multiplayer sync issues  
**Mitigation:** Turn-based = easier sync, defer to Phase 3

---

## 12. Timeline Estimate

**Phase 1 (Design):** 1 week  
- GDD ✅
- Spell/item/monster data: 3 days
- Campaign template: 2 days

**Phase 2 (MVP Backend):** 2-3 weeks  
- Rules engine: 4 days
- Combat engine: 3 days
- DM agent: 5 days
- NPC agent: 3 days
- Map generator: 3 days
- Testing: 2 days

**Phase 3 (Client):** TBD (separate project)

---

## 13. Next Steps

1. **Review this GDD** — Mami feedback
2. **Write spell database** (50 spells, JSON)
3. **Write item database** (weapons, armor, potions)
4. **Write monster bestiary** (20 creatures, stats)
5. **Start Phase 2:** `rules.py` + `combat.py`

---

**End of GDD v0.1**

Mami, bu taslak. Feedback ver:
- Kural sistemi yeterince basit/açık mı?
- AI agent görevleri net mi?
- Eksik bir şey var mı?

Onayından sonra spell/item/monster DB'lerini yazıp Phase 2'ye geçerim.
