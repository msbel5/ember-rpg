# PRD: Save/Load System — Ember RPG Backend

**Version:** 1.1  
**Author:** Alcyone  
**Date:** 2026-03-25  
**Status:** Implemented

---

## 1. Overview & Goals

The save/load system persists the full `GameSession` so a player can resume exactly where the simulation left off. The same serializer now powers autosave, manual save/load, restore-on-restart, REST routes, and natural-language engine commands.

**Goals:**
- Persist full session state as JSON on disk
- Use named save slots as the canonical save model
- Restore per-session autosaves after restart
- Expose `save/load/list/delete` through REST and engine intents
- Preserve combat, world simulation, inventory/equipment, quest, and narration fidelity

---

## 2. Functional Requirements

| ID | Requirement |
|----|-------------|
| FR-01 | The system SHALL save a session to `saves/<slot_name>.json`. |
| FR-02 | The save payload SHALL include `slot_name`, `player_name`, `session_state`, `timestamp`, `schema_version`, and session metadata. |
| FR-03 | The serializer SHALL preserve combat state, map state, spatial entities, schedules, patrol routes, body trackers, fog, rumors, quests, inventory/equipment metadata, and narration context. |
| FR-04 | The system SHALL support manual named slots via REST and natural-language commands such as `save`, `save as <slot>`, and `load <slot>`. |
| FR-05 | The system SHALL support per-session autosave slots used for restore-on-restart. |
| FR-06 | Ordinary session lookup SHALL restore from autosave only; manual saves are loaded explicitly. |
| FR-07 | The system SHALL list saves globally or filtered by player name. |
| FR-08 | The system SHALL delete a save by slot name. |
| FR-09 | Loading a missing slot SHALL raise a missing-save error / return a clear user-facing message. |
| FR-10 | Loading corrupt JSON SHALL raise a corrupt-save error. |

---

## 3. Non-Functional Requirements

- **Performance:** Save/load should complete in < 250ms for typical sessions.
- **Reliability:** Writes must be atomic enough to avoid partial slot corruption.
- **Portability:** Save files remain plain JSON.
- **Compatibility:** Legacy route contracts may keep `save_id` as a field name, but it maps to the canonical slot name.
- **Testability:** Save behavior must be testable without a running server.

---

## 4. Architecture & Data Model

### Directory Layout

```text
frp-backend/
  saves/                  # runtime save files (git-ignored)
  engine/
    api/
      save_system.py      # canonical serializer/deserializer
      save_routes.py      # REST compatibility facade
```

### Save File Format

```json
{
  "slot_name": "quicksave",
  "player_name": "Aria",
  "timestamp": "2026-03-25T17:00:00",
  "schema_version": "1.0",
  "location": "Harbor Town",
  "game_time": "Day 2 Hour 9",
  "session_state": {
    "session_id": "uuid",
    "player": {},
    "combat": {},
    "inventory": [],
    "equipment": {},
    "quest_offers": [],
    "campaign_state": {},
    "narration_context": {}
  }
}
```

### Naming

- Manual slots: `quicksave`, `before_mines`, `merchant_run_2`
- Autosave slots: `autosave_<session_id>`

---

## 5. Public API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/game/session/{session_id}/save` | Save current session to a slot |
| GET | `/game/saves/{player_id}` | List saves for a player |
| GET | `/game/saves/file/{save_id}` | Get slot metadata |
| DELETE | `/game/saves/{save_id}` | Delete a slot |
| POST | `/game/session/load/{save_id}` | Load a session from a slot |

### Engine Commands

- `save`
- `save as <slot>`
- `load <slot>`
- `list saves`
- `delete save <slot>`

These commands do not advance the world tick.

---

## 6. Acceptance Criteria

| AC | Maps to | Criteria |
|----|---------|----------|
| AC-01 | FR-01 | Saving creates `saves/<slot>.json`. |
| AC-02 | FR-03 | Load restores combat, entities, quests, inventory/equipment, and position losslessly. |
| AC-03 | FR-04 | Engine save/load/list/delete intents work with named slots. |
| AC-04 | FR-05 | Autosaves are written after player actions and can restore a session after restart. |
| AC-05 | FR-06 | Deleting a live session does not auto-restore it from a manual save slot. |
| AC-06 | FR-07 | Listing returns filtered saves for the specified player. |
| AC-07 | FR-08 | Deleting a slot removes it from disk and from subsequent listings. |
| AC-08 | FR-09 | Missing slots return a clear error. |
| AC-09 | FR-10 | Corrupt JSON returns a clear corruption error. |

---

## 7. Edge Cases

- Re-saving an existing slot overwrites it atomically.
- Sessions with no quests/combat still serialize as valid minimal saves.
- Missing `saves/` directory is created automatically.
- Manual saves remain available after a session is ended, but they are not used for implicit session restore.
- Route compatibility keeps `save_id` in responses even though the backing model is slot-based.

---

## 8. Security Considerations

- Slot names are sanitized before being used as filenames.
- No authentication is enforced in v1.
- Save files are intended for single-user/self-hosted deployments.

---

## 9. Future Extensions

- Cloud or database-backed save providers behind the same interface
- Save migration tooling for future schema versions
- Richer slot metadata such as screenshots or labels
- Compression for very large campaigns

---

## 10. Out of Scope

- Authentication / authorization
- Cloud sync
- Encryption
- Multiplayer save coordination
- Frontend save-slot UI
