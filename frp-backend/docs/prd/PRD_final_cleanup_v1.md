# PRD: Final Legacy Cleanup

**Version:** 1.0
**Date:** 2026-04-03
**Phase:** Post-migration cleanup
**Status:** Active

## Objective

Eliminate all remaining legacy `engine.core` references across the entire
codebase -- tests, tools, and kernel files. After this phase, `grep -r
"from engine.core" --include="*.py"` returns ZERO results outside of
guardrail test strings.

## Scope

### 1. Delete Dead Legacy Test Files (27 files)

Test files that directly `import` from `engine.core` modules which no
longer exist. These tests are permanently broken and test deleted code.

**Files to delete:**
- test_api.py, test_character.py, test_combat.py, test_combat_spell.py
- test_combat_overhaul.py, test_coverage_boost.py, test_coverage_gaps.py
- test_chaos_session.py, test_combat_flow.py, test_dm_agent.py
- test_data_driven_audit.py, test_effect.py, test_enemy_ai.py
- test_game_engine.py, test_item.py, test_loot.py, test_monster.py
- test_progression.py, test_rules.py, test_spell.py
- test_zone_integration.py, test_physical_inventory_integration.py
- test_llm_integration.py, test_save_system.py
- test_npc_memory_persistence.py, test_campaign_creation_wizard.py
- test_campaign_templates.py

**NOT deleted** (contain "engine.core" only as pattern strings, not imports):
- test_legacy_detection.py (guardrail scanner)
- test_kernel_adapter.py (AST import checker)

### 2. Fix tools/ Files (3 files)

Replace `from engine.core.character_creation` with kernel equivalents:

| File | Legacy Import | Kernel Replacement |
|------|--------------|-------------------|
| campaign_client.py | ABILITY_ORDER, assign_stats_to_class | engine.kernel.creation |
| play_topdown.py | ABILITY_ORDER, assign_stats_to_class, get_creation_catalog | engine.kernel.creation |
| play_topdown_view.py | ABILITY_ORDER, assign_stats_to_class | engine.kernel.creation |

### 3. Remove Stat Fallbacks in Kernel (2 files)

**combat_wounds.py:54-55** -- Remove lowercase "strength"/"agility" fallbacks:
```python
# BEFORE
mig = int(attacker.stats.get("MIG", attacker.stats.get("strength", 10)))
agi = int(attacker.stats.get("AGI", attacker.stats.get("agility", 10)))
# AFTER
mig = int(attacker.stats.get("MIG", 10))
agi = int(attacker.stats.get("AGI", 10))
```

**systems_syndromes.py:122-123** -- Remove case-variant fallbacks:
```python
# BEFORE
disease_resistance = int(actor.stats.get("disease_resistance", actor.stats.get("DISEASE_RESISTANCE", 0)))
toughness = int(actor.stats.get("TOUGHNESS", actor.stats.get("END", 10)))
# AFTER
disease_resistance = int(actor.stats.get("disease_resistance", 0))
toughness = int(actor.stats.get("END", 10))
```

### 4. Wire QUALITY_MULTIPLIERS to data_loader.py

Replace hardcoded dict in `combat_types.py` with a call to
`load_quality_tiers()` from `engine.kernel.data_loader`. The JSON file
`data/quality_tiers.json` already contains the exact same values.

### 5. Simplify effects.py Alias Map

The `_stat_lookup()` function in `effects.py:418-445` contains D&D stat
name aliases (con, constitution, dex, dexterity, etc.) that map to Ember
keys. Since all kernel code now uses Ember-only stat names, reduce this
to a minimal lowercase-to-uppercase mapping without D&D vocabulary.

### 6. Update Guardrail Tests

Extend `test_legacy_detection.py` to also scan `tests/` and `tools/`
directories for stale `engine.core` imports.

## Acceptance Criteria

1. `grep -r "from engine.core" --include="*.py"` returns ZERO results
   (outside of pattern-matching strings in guardrail tests)
2. All remaining tests pass: `pytest tests/ -q` with 0 errors
3. No hardcoded `QUALITY_MULTIPLIERS` dict in kernel Python code
4. No D&D stat names (STR/DEX/CON/INT/WIS/CHA, strength/dexterity/etc.)
   used as primary lookup keys in kernel code
5. `tools/campaign_client.py` works with kernel imports

## Non-Goals

- Rewriting deleted test logic for kernel (future task)
- Adding new tests for tools/ CLI utilities
- Changing any game mechanics or behavior
