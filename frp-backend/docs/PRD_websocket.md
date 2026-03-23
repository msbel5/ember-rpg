# PRD: WebSocket Real-Time Events — Ember RPG Backend

**Version:** 1.0  
**Author:** Alcyone (Subagent)  
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
