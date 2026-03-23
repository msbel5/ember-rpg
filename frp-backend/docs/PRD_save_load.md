# PRD: Save/Load System — Ember RPG Backend

**Version:** 1.0  
**Author:** Alcyone (Subagent)  
**Date:** 2026-03-23  
**Status:** Approved

---

## 1. Overview & Goals

The Save/Load system allows players to persist their game session state to disk, resume from a saved state, and manage multiple save files. This enables asynchronous play (start now, continue later) and protects against session loss due to disconnects or server restarts.

**Goals:**
- Persist full session state as JSON on disk
- Provide CRUD REST endpoints for save management
- Support auto-save on every player action
- Ensure thread-safe file operations for concurrent sessions
- Version save files for future schema migrations

---

## 2. Functional Requirements

| ID    | Requirement |
|-------|-------------|
| FR-01 | The system SHALL save a session's state to a JSON file in the `saves/` directory |
| FR-02 | Each save file SHALL include: `save_id`, `player_id`, `session_data`, `timestamp`, `schema_version` |
| FR-03 | The system SHALL return a unique `save_id` upon successful save |
| FR-04 | The system SHALL load (restore) session state from a save file given a `save_id` |
| FR-05 | The system SHALL list all saves belonging to a given `player_id` |
| FR-06 | The system SHALL delete a save file by `save_id` |
| FR-07 | Auto-save SHALL be triggered after every player action (configurable flag) |
| FR-08 | Thread-safe file writes SHALL be enforced via per-save-id file locks |
| FR-09 | `schema_version` SHALL be set to `"1.0"` for all saves created by this system |
| FR-10 | Loading a non-existent save SHALL raise a `SaveNotFoundError` |
| FR-11 | Loading a corrupt/invalid JSON save SHALL raise a `CorruptSaveError` |

---

## 3. Non-Functional Requirements

- **Performance:** Save/load operations complete in < 200ms for session data up to 1MB
- **Reliability:** File writes are atomic (write-to-temp then rename) to prevent partial saves
- **Portability:** Save files are plain JSON; no binary formats
- **Testability:** SaveManager is fully unit-testable without a live FastAPI server
- **Scalability:** Save directory supports thousands of save files (flat directory with player-prefixed filenames)

---

## 4. Architecture & Data Model

### Directory Layout
```
frp-backend/
  saves/                  # runtime save files (git-ignored)
  engine/
    save/
      __init__.py         # SaveManager class
      save_models.py      # SaveFile dataclass/Pydantic model
    api/
      save_routes.py      # FastAPI router
```

### Save File Format (JSON)
```json
{
  "save_id": "550e8400-e29b-41d4-a716-446655440000",
  "player_id": "player_123",
  "session_data": { ... },
  "timestamp": "2026-03-23T12:00:00",
  "schema_version": "1.0"
}
```

### File Naming Convention
`saves/{player_id}_{save_id}.json`

### Thread Safety
`threading.Lock` per `save_id` (keyed dict of locks in `SaveManager`).

---

## 5. API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/game/session/{session_id}/save` | Save current session state |
| GET    | `/game/saves/{player_id}` | List all saves for a player |
| GET    | `/game/saves/file/{save_id}` | Get a specific save by ID |
| DELETE | `/game/saves/{save_id}` | Delete a save |
| POST   | `/game/session/load/{save_id}` | Load session from a save |

### Request/Response Examples

**POST /game/session/{session_id}/save**
- Body: `{ "player_id": "player_123" }`
- Response: `{ "save_id": "uuid", "timestamp": "...", "schema_version": "1.0" }`

**GET /game/saves/{player_id}**
- Response: `[ { "save_id": "...", "timestamp": "...", "schema_version": "1.0" }, ... ]`

**POST /game/session/load/{save_id}**
- Response: `{ "session_id": "...", "status": "loaded", "session_data": { ... } }`

---

## 6. Acceptance Criteria

| AC    | Maps to | Criteria |
|-------|---------|----------|
| AC-01 | FR-01   | Calling save creates a `.json` file in `saves/` |
| AC-02 | FR-03   | Save response contains a non-empty `save_id` string |
| AC-03 | FR-04   | Loaded `session_data` matches what was saved |
| AC-04 | FR-05   | List endpoint returns only saves for the given `player_id` |
| AC-05 | FR-06   | After delete, the save file no longer exists on disk |
| AC-06 | FR-10   | Loading a non-existent save raises `SaveNotFoundError` |
| AC-07 | FR-11   | Loading a file with invalid JSON raises `CorruptSaveError` |
| AC-08 | FR-09   | Every save file contains `schema_version == "1.0"` |

---

## 7. Edge Cases

- **Concurrent saves for same player:** Each save gets a unique `save_id`; no overwrite
- **Empty session_data:** Allowed; saves empty dict `{}`
- **Player with no saves:** List returns empty list `[]`
- **Delete non-existent save:** Raises `SaveNotFoundError`
- **saves/ directory missing:** `SaveManager.__init__` creates it automatically
- **Corrupt file (truncated JSON):** Detected on load; raises `CorruptSaveError`
- **Very large session_data:** No artificial size cap; OS file limits apply

---

## 8. Security Considerations

- **Path traversal:** `player_id` and `save_id` are sanitized (alphanumeric + `-_` only) before use in filenames
- **No authentication in v1:** All endpoints are open; authentication is out of scope (see Section 10)
- **No secrets in session_data:** Caller responsibility; SaveManager does not inspect content
- **File permissions:** `saves/` directory created with default umask; world-readable acceptable for single-user local server

---

## 9. Future Extensions

- **Cloud save hooks:** Abstract `SaveManager` behind a `SaveBackend` protocol; swap local JSON for S3/GCS
- **Multiplayer:** Tag saves with `session_id` + multiple `player_id`s; support shared session snapshots
- **Schema migration:** `schema_version` field enables version-gated migration scripts (`migrate_1_0_to_1_1.py`)
- **Compression:** Gzip large session blobs to reduce disk I/O
- **Save slots UI:** Named save slots ("Before Boss Fight") stored as metadata alongside `save_id`
- **Incremental saves:** Diff-based saves to store only changed state fields

---

## 10. Out of Scope

- User authentication / authorization
- Cloud or remote storage backends
- Save encryption
- Real-time sync between clients
- Save file compression
- GUI or frontend for save management
- Database-backed saves (PostgreSQL, SQLite)
- Automatic purging of old saves
