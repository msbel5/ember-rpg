# PRD: WebSocket Real-Time Events — Ember RPG Backend
**Project:** Ember RPG  
**Phase:** 2  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Draft

---

## 1. Overview & Goals

The WebSocket system replaces HTTP polling for real-time game events, providing low-latency bidirectional communication between clients and the Ember RPG backend. This is the foundation for live DM narratives, instant combat feedback, and future multiplayer support.

**Goals:**
- Push game events to connected clients instantly (no polling)
- Support multiple clients subscribed to the same session (multiplayer groundwork)
- Define a clean event protocol for all game event types
- Provide a migration path from existing REST endpoints
- Keep the WebSocket layer thin — game logic stays in the engine

---

## 2. Event Types

All messages are JSON objects with a `type` field.

### Server → Client Events

| Event Type | Payload Fields | Description |
|------------|---------------|-------------|
| `action_result` | `session_id`, `narrative`, `player_state`, `effects` | Result of a player action processed by the engine |
| `combat_update` | `session_id`, `round`, `combatants`, `last_action`, `combat_ended` | Combat state update after any action |
| `dm_narrative` | `session_id`, `text`, `scene_type`, `location` | DM narration event (atmosphere, discovery, transition) |
| `session_state` | `session_id`, full session dict | Full session snapshot (sent on subscribe or resync request) |
| `error` | `code`, `message` | Protocol or engine error |
| `pong` | — | Keepalive response |

### Client → Server Messages

| Message Type | Payload Fields | Description |
|-------------|---------------|-------------|
| `subscribe` | `session_id` | Subscribe to events for a session |
| `unsubscribe` | `session_id` | Stop receiving events for a session |
| `action` | `session_id`, `text` | Submit a player action (replaces POST /game/session/{id}/action) |
| `ping` | — | Keepalive request |
| `resync` | `session_id` | Request a fresh `session_state` snapshot |

---

## 3. Connection Lifecycle

```
Client                          Server
  |                               |
  |--- WS connect /ws/game ------>|
  |<-- connection accepted -------|
  |                               |
  |--- { type: "subscribe",       |
  |      session_id: "abc" } ---->|
  |<-- { type: "session_state",   |
  |      ...full state... } ------|
  |                               |
  |--- { type: "action",          |
  |      session_id: "abc",       |
  |      text: "attack goblin" }->|
  |<-- { type: "action_result",   |
  |      narrative: "...",        |
  |      player_state: {...} } ---|
  |<-- { type: "combat_update",   |
  |      round: 1, ... } ---------|
  |                               |
  |--- { type: "ping" } --------->|
  |<-- { type: "pong" } ----------|
  |                               |
  |--- { type: "unsubscribe",     |
  |      session_id: "abc" } ---->|
  |--- WS close ----------------->|
```

---

## 4. WebSocket Endpoint

**URL:** `ws://{host}/ws/game`  
**Protocol:** Plain WebSocket (no subprotocol negotiation in v1)  
**Authentication:** None in v1 (token-based auth planned for v2)

A single multiplexed endpoint handles all sessions. Clients subscribe to specific sessions by `session_id`.

---

## 5. Multiplayer Groundwork

- **Session registry:** `ConnectionManager` maintains a mapping of `session_id → List[WebSocket]`
- **Broadcast:** When any engine event fires, the `ConnectionManager` broadcasts to all subscribers
- **Isolation:** Clients only receive events for sessions they have subscribed to
- **Concurrency:** `asyncio.Lock` per session for safe concurrent fan-out
- **Scale note:** This in-process registry works for single-node deployments; Redis pub/sub is the scale-out path (see Section 9)

```python
# Conceptual structure
class ConnectionManager:
    def __init__(self):
        self.subscriptions: dict[str, list[WebSocket]] = {}

    async def subscribe(self, session_id: str, ws: WebSocket): ...
    async def unsubscribe(self, session_id: str, ws: WebSocket): ...
    async def broadcast(self, session_id: str, event: dict): ...
```

---

## 6. FastAPI WebSocket Implementation

### File Layout
```
engine/
  api/
    ws_manager.py     # ConnectionManager class
    ws_routes.py      # WebSocket endpoint
main.py               # mount ws_routes
```

### Key FastAPI Patterns

```python
from fastapi import WebSocket, WebSocketDisconnect
from engine.api.ws_manager import ConnectionManager

manager = ConnectionManager()

@router.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "subscribe":
                await manager.subscribe(data["session_id"], websocket)
                # Send session_state snapshot
            elif msg_type == "action":
                result = engine.process_action(...)
                await manager.broadcast(data["session_id"], {
                    "type": "action_result", ...
                })
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.remove_all_subscriptions(websocket)
```

### Event Emission Integration

The engine's `process_action` method will emit a list of typed events. The WebSocket layer maps these to the event schema above. No engine changes are needed for pure single-player WebSocket; multiplayer requires the engine to be session-aware (already is).

---

## 7. Migration Path from REST Endpoints

| Old REST Endpoint | WebSocket Replacement | Notes |
|-------------------|-----------------------|-------|
| `POST /game/session/{id}/action` | `{ type: "action", session_id, text }` | REST endpoint stays for backward compatibility |
| `GET /game/session/{id}` | `{ type: "resync", session_id }` → `session_state` | REST stays; WS adds push |
| `POST /game/session/new` | Still REST (one-time setup, not real-time) | No WS replacement needed |
| Save/Load endpoints | Still REST (not real-time operations) | No WS replacement needed |

**Migration strategy:** REST endpoints are NOT removed. WebSocket is additive. Clients opt in to WS. Over time, polling clients are migrated by updating client code to connect via WS instead of polling `GET /game/session/{id}`.

---

## 8. Acceptance Criteria (for implementation phase)

| AC    | Criteria |
|-------|----------|
| AC-WS-01 | Client can connect to `ws://{host}/ws/game` |
| AC-WS-02 | After `subscribe`, client receives `session_state` snapshot |
| AC-WS-03 | Submitting an `action` message triggers `action_result` event to all session subscribers |
| AC-WS-04 | Combat actions trigger a `combat_update` event |
| AC-WS-05 | `ping` → `pong` round-trip works |
| AC-WS-06 | Disconnected clients are cleaned up from all subscriptions |
| AC-WS-07 | Two clients subscribed to same session both receive broadcast events |
| AC-WS-08 | Client subscribed to session A does NOT receive events for session B |

---

## 9. Future Extensions

- **Redis pub/sub backend:** Replace in-process `ConnectionManager` with Redis channels for horizontal scaling
- **Authentication:** JWT token in WebSocket handshake headers (`Authorization: Bearer ...`)
- **Presence events:** `player_joined`, `player_left` for multiplayer lobbies
- **Spectator mode:** Read-only subscription to a session
- **Binary protocol:** MessagePack instead of JSON for bandwidth reduction
- **Reconnect with replay:** Store last N events per session; replay on reconnect with `last_event_id`

---

## 10. Out of Scope

- WebSocket authentication (v1)
- Redis or external pub/sub
- Binary/MessagePack protocol
- Client SDK / JavaScript wrapper
- Load balancing / sticky sessions
- Rate limiting per WebSocket connection
- Presence / player roster management
- Voice or video channels

---

## 11. Functional Requirements

**FR-01:** The WebSocket endpoint `ws://{host}/ws/game` must accept connections and respond to all 5 message types: `subscribe`, `unsubscribe`, `action`, `ping`, `resync`.

**FR-02:** After a `subscribe` message, the server must immediately send a `session_state` snapshot to the subscribing client.

**FR-03:** When `action` is submitted via WebSocket, the engine must process it and broadcast an `action_result` event to ALL clients subscribed to that session.

**FR-04:** Combat actions must trigger a `combat_update` event broadcast to all subscribers of the session.

**FR-05:** `ping` messages must receive a `pong` response within 1 second.

**FR-06:** On WebSocket disconnect, the server must remove the client from all subscriptions without affecting other subscribers.

**FR-07:** A client subscribed to session A must NOT receive events for session B (session isolation).

**FR-08:** Two clients subscribed to the same session must both receive broadcast events (fan-out).

**FR-09:** REST endpoints (`POST /action`, `GET /session`) must remain functional alongside WebSocket (additive, not replacing).

**FR-10:** Concurrent action submissions from multiple clients on the same session must be handled safely (asyncio.Lock per session).

---

## 12. Data Structures

```python
# All messages are JSON dicts with a "type" field

# Client → Server
Subscribe = {"type": "subscribe", "session_id": str}
Unsubscribe = {"type": "unsubscribe", "session_id": str}
Action = {"type": "action", "session_id": str, "text": str}
Ping = {"type": "ping"}
Resync = {"type": "resync", "session_id": str}

# Server → Client
ActionResult = {"type": "action_result", "session_id": str, "narrative": str,
                "player_state": dict, "effects": list}
CombatUpdate = {"type": "combat_update", "session_id": str, "round": int,
                "combatants": list, "last_action": dict, "combat_ended": bool}
DMNarrative = {"type": "dm_narrative", "session_id": str, "text": str,
               "scene_type": str, "location": str}
SessionState = {"type": "session_state", "session_id": str, ...}
Error = {"type": "error", "code": str, "message": str}
Pong = {"type": "pong"}
```

---

## 13. Public API

```python
# ConnectionManager
class ConnectionManager:
    def __init__(self)
    async def subscribe(self, session_id: str, ws: WebSocket) -> None
    async def unsubscribe(self, session_id: str, ws: WebSocket) -> None
    async def broadcast(self, session_id: str, event: dict) -> None
        """Sends event to all WebSockets subscribed to session_id. Handles dead connections gracefully."""
    def remove_all_subscriptions(self, ws: WebSocket) -> None
        """Called on disconnect to clean up all session subscriptions for this WebSocket."""

# FastAPI route
@router.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket): ...
```

---

## 14. Acceptance Criteria (Standard Format)

AC-01 [FR-01]: Given a running server, when a client connects to `ws://{host}/ws/game`, then the connection is accepted without error.

AC-02 [FR-02]: Given a connected client, when it sends `{"type": "subscribe", "session_id": "abc"}`, then it receives a `session_state` message within 500ms.

AC-03 [FR-03]: Given two clients A and B both subscribed to session "abc", when client A sends an `action` message, then both A and B receive an `action_result` event.

AC-04 [FR-04]: Given a session in combat, when any action triggers a combat state change, then a `combat_update` event is broadcast to all subscribers.

AC-05 [FR-05]: Given a connected client, when it sends `{"type": "ping"}`, then it receives `{"type": "pong"}` within 1 second.

AC-06 [FR-06]: Given two clients subscribed to the same session, when one disconnects, then the other continues to receive events without error.

AC-07 [FR-07]: Given client A subscribed to session "abc" and client B subscribed to session "xyz", when an action is processed for session "abc", then client B receives no events.

AC-08 [FR-09]: Given a running WebSocket server, when `POST /game/session/{id}/action` is called via HTTP, then it returns a response normally (REST not broken by WS).

---

## 15. Performance Requirements

- `ping` → `pong` round-trip: < 1 second
- Action broadcast to 10 subscribers: < 50ms
- Subscribe + session_state delivery: < 500ms
- Disconnect cleanup: < 10ms

---

## 16. Error Handling

| Condition | Behavior |
|---|---|
| Unknown message type | Send `{"type": "error", "code": "UNKNOWN_MSG", "message": "..."}` |
| `action` on non-existent session | Send `{"type": "error", "code": "SESSION_NOT_FOUND"}` |
| Subscriber WebSocket dead during broadcast | Remove from subscription silently, continue broadcast to others |
| Malformed JSON received | Send error event, do not crash the handler |
| Concurrent actions on same session | asyncio.Lock per session prevents race condition |

---

## 17. Integration Points

- **GameEngine:** `process_action()` called from WebSocket handler; events emitted after processing
- **REST API Layer:** WebSocket is additive; both share the same in-memory session store
- **Session Store:** `ConnectionManager.subscriptions` keyed by `session_id`
- **Future: Redis pub/sub** — scale-out path when multi-node deployment needed

---

## 18. Test Coverage Target

- **Target:** ≥ 90% line coverage using FastAPI's `TestClient` with WebSocket support
- **Must cover:** subscribe/broadcast flow, session isolation (two sessions), disconnect cleanup, unknown message type error, concurrent action safety
