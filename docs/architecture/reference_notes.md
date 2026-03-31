# Reference Notes

## Dwarf Fortress

- Value to borrow: macro simulation with deep history and local detail only
  where needed
- Do not borrow: source structure from unofficial mirrors

## RimWorld

- Value to borrow: one active map, abstract world layer, visible needs/jobs,
  no-LLM core simulation
- Do not borrow: decompiled implementation details as project code

## Ember Translation

- Deterministic simulation stays authoritative
- AI remains optional narration/conversation enrichment only
- World graph + one active local map is the correct runtime split
- Creation answers should shape:
  - world tone
  - colony pressure
  - faction bias
  - settlement bias
  - opening quest themes
