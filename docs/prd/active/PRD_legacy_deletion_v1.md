# PRD: Legacy Deletion v1

**Status:** Implemented (Partial)
**Phase:** 7
**Date:** 2026-04-03

## Summary

Delete confirmed dead legacy modules from engine/core/ and add guardrail
tests that prevent legacy import count from increasing.

## Deleted Files (5)
- `engine/core/campaign.py` -- unused campaign state
- `engine/core/loot.py` -- unused loot generation
- `engine/core/monster.py` -- replaced by create_monster_actor()
- `engine/core/npc.py` -- unused NPC base class
- `engine/core/rules.py` -- unused dice rolling (kernel has its own)

## Kept (Still in import chain)
- `engine/core/character.py` -- 13 imports via session/handlers
- `engine/core/combat.py` -- 5 imports via handlers (needs enemy_ai.py)
- `engine/core/dm_agent.py` -- 15 imports (narrator system)
- `engine/core/character_creation.py` -- 4 imports (creation wizard)
- `engine/core/enemy_ai.py` -- required by combat.py import chain
- Others with 1-3 imports

## Guardrails
- Legacy import ceiling: 60 (will decrease as handlers are rewritten)
- Kernel files must never import engine.core (verified by AST scan)
- Dead files verified deleted in test suite
