# Ember RPG — Final D&D Systems Implementation + 100-Turn Chaos Test

## Your Mission

Read `docs/PRD_dnd_systems_v1.md` first — it contains the full design for 10 missing D&D systems with 5 implementation sprints. Then implement ALL sprints, test, play a 100-turn chaotic session, fix everything, and push.

## Sprint Order

### Sprint 1: Foundations
- Add `proficiency_bonus` to Character: `(level - 1) // 4 + 2`
- Add `skill_proficiencies: List[str]` per class (warrior picks 2 from Athletics/Intimidation/Perception/Survival, rogue picks 4, etc.)
- Check formula: `d20 + ability_mod + (prof_bonus if proficient)`
- **Passive checks**: `passive_perception = 10 + WIS_mod + (prof if proficient)`, same for Investigation (INT) and Insight (WIS)
- **Advantage/Disadvantage**: Roll 2d20, take higher/lower. Add `advantage/disadvantage` params to all d20 roll functions.
- **CRITICAL DM FIX**: Update DM system prompt to include passive scores. Add this rule: "Player's passive Perception is {X}. Only mention hidden details if their DC <= {X}. Most places are ordinary. Do NOT fabricate secret passages or hidden items unless location data explicitly marks them."

### Sprint 2: Conditions & Rest
- Expand Condition to enum with all 15 D&D conditions (Blinded, Charmed, Deafened, Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Petrified, Poisoned, Prone, Restrained, Stunned, Unconscious)
- Each condition has mechanical effects on combat (advantage/disadvantage on rolls)
- **Exhaustion**: 6 levels (disadvantage checks → half speed → disadvantage attacks → half HP → speed 0 → death). Reduced by long rest.
- **Short Rest** (`rest` or `short rest`): 1 game-hour, spend Hit Dice to heal (warrior d10, rogue d8, mage d6, priest d8). Track hit_dice_remaining.
- **Long Rest** (`long rest` or `sleep` or `camp`): 8 hours, full HP, regain half Hit Dice, -1 exhaustion. Max once per 24 game-hours.

### Sprint 3: Social & Conversation
- **NPC attitudes**: Add `attitude: str` (friendly/indifferent/hostile) to entities. Default: indifferent.
- **Social DCs**: Friendly+no risk=auto, Indifferent+no risk=DC 10, Hostile+no risk=DC 20. Scale up for risky requests.
- **Bribe**: Persuasion check, DC lowered by gift value. Success shifts attitude one step friendlier.
- **Intimidate**: Contested check (attacker PRE vs defender INS). Success: target does what you want (but shifts hostile).
- **Deceive**: Deception check vs target's Passive Insight. Success: target believes the lie.
- **Crime consequences**: Attack/steal near witnesses → all witnesses shift to Hostile. Guards alerted.
- **Conversation targets**:
  - Default: DM (commands, questions, actions)
  - `talk to <NPC>`: switches active conversation partner
  - `think` / `to self` / `recall`: internal monologue → DM triggers appropriate skill check (History/Arcana/Religion/Nature based on topic). Crit = deep knowledge, near miss = vague, fail = nothing.
  - **Eavesdroppers**: NPCs within 2 tiles hear conversations. Crime discussed near guard = guard reacts.
- Add parser intents: `THINK`, `ADDRESS`

### Sprint 4: Combat Polish
- **Initiative**: d20 + AGI_mod at combat start. Sort combatants highest first. DEX breaks ties.
- **Death saves**: At 0 HP → Unconscious, not dead. Each turn: d20 DC 10. Nat 20 = 1 HP. Nat 1 = 2 failures. 3 successes = stabilized. 3 failures = dead.
- **Opportunity attacks**: When fleeing without Disengage action, enemy gets one free attack.
- **Disengage**: New action — flee safely without opportunity attack (costs your Action).
- **Alignment**: Add 9-alignment system (LG/NG/CG/LN/TN/CN/LE/NE/CE) to characters and NPCs. Affects NPC reactions and quest availability. Player alignment shifts from actions.

### Sprint 5: Integration, Wire & Test
- Wire ALL new systems into `game_engine.py` handlers
- Update `save_system.py` for new fields (proficiencies, conditions, attitude, alignment, hit dice, death saves)
- Update `play_topdown.py` status display to show conditions, alignment
- Update `action_parser.py` with new intents (THINK, SHORT_REST, LONG_REST, DISENGAGE)
- Run full test suite — all must pass
- **Play 100-turn chaos session** (see below)

## 100-Turn Chaos Play-Test

After implementing all sprints, play a full session programmatically (100+ actions). The character should:

**Act 1 (turns 1-15): Arrive & Explore**
- Create a rogue, look around, map the town
- Approach every NPC, talk to each one
- Check passive Perception — does DM describe only appropriate details?

**Act 2 (turns 16-30): Social Games**
- Try to deceive a merchant ("I'm the mayor's envoy")
- Intimidate a beggar
- Bribe a guard
- Persuade a blacksmith to give a discount
- Think "what do I know about this town's history?" — check History skill
- Eavesdrop on NPC conversation

**Act 3 (turns 31-50): Crime Spree**
- Steal from merchant → check if witnesses react
- Attack merchant → check if guard intervenes
- Fight guard → take damage, check death saves if HP hits 0
- Flee → check opportunity attack
- Try Disengage → flee safely
- Check NPC attitudes after crimes (should be hostile)
- Try to talk to hostile NPCs

**Act 4 (turns 51-70): Recovery & Rest**
- Short rest — spend hit dice to heal
- Long rest — full recovery, check exhaustion clears
- Accept quest from friendly NPC
- Complete quest objectives
- Turn in quest
- Check reputation/attitude improvements

**Act 5 (turns 71-100): World Endurance**
- Keep playing, testing all systems
- Save game, load game, verify all new state survives
- Check alignment shifts from actions
- Try to change NPC attitude from hostile to indifferent
- Test every parser intent
- Verify world tick still works with new systems

**Log every action with:** command, narrative, HP, AP, conditions, attitude changes, skill checks, passive checks.

## How to Run

```bash
cd frp-backend
pip install -r requirements.txt
python -m pytest tests/ -q          # All tests must pass
python -m tools.play_topdown        # Play the game
```

## Attitude

This is the FINAL implementation pass. After this, the game must be a complete, playable FRP experience. Every action traceable to character attributes. Every NPC reaction consistent with attitude and alignment. Every skill check following D&D formula. No more generic narration. No more fabricated hidden details. A real, living, deterministic world with AI narration on top.
