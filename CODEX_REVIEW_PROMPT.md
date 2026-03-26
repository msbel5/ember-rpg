# Ember RPG — Final Review, Fix & Play Prompt

## Current State

- **1884 tests passing** (1 flaky chaos test, non-blocking)
- game_engine.py refactored into 8 mixin files (~700 lines each)
- Data-driven: classes loaded from `data/classes.json`
- D&D systems implemented: proficiency, passive checks, advantage/disadvantage, 15 conditions, exhaustion, short/long rest, NPC attitudes, social DCs, conversation targets, THINK intent, initiative, death saves, opportunity attacks, disengage, alignment

## What to Do

1. **Strict senior review** You should test every part of the back end no gap or inconsistencies should exist
'. **Documentation and Testing** You should read and understand the game logic and vision and test it accordingly
3. **Play-test 100 turns** programmatically and fix every bug found

## Play-Test Requirements

The 500-turn session must cover:

- Explore and approach every NPC (**verify approach works**)
- Talk, persuade, bribe, deceive, intimidate (**verify social range**)
- THINK about various topics (History, Arcana, Religion)
- Combat: attack, disengage, flee, death saves
- Short rest, long rest
- Craft something
- Accept quest, complete quest, turn in quest
- Save and load (**verify state preserved**)
- Steal from merchant (**verify crime consequences**)
- Check passive Perception reveals
- Check alignment shifts
- İf you found a bug take note of it. Fix it after the game finishes then Play-test again
- Continu this cycle until there are no bugs in project and our quality matched with AAA games.

## How to Run

```bash
cd frp-backend
pip install -r requirements.txt
python -m pytest tests/ -q          # 1884 tests
python -m tools.play_topdown        # Play interactively
```

## Attitude

Fix bugs first. Then play-test. Ship a game that works from turn 1. No "too far away" on the first NPC interaction. No walls trapping the player. A game where approach → talk → quest → adventure flows naturally.
