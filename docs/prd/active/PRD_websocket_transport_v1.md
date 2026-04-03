# PRD: WebSocket Transport v1

**Status:** In Progress
**Phase:** 3
**Date:** 2026-04-03

## Summary

Add WebSocket transport for real-time bidirectional communication between
the Godot client and Python backend. The client sends commands, the server
pushes state snapshots and world events.

## Design

### Server: `engine/api/ws_campaign.py`
- WebSocket endpoint: `GET /game/ws/campaigns/{campaign_id}`
- Message protocol (JSON):
  - Client -> Server: `{"type": "command", "input": "attack goblin"}`
  - Server -> Client: `{"type": "state", "snapshot": {...}}`
  - Server -> Client: `{"type": "event", "events": [...]}`
  - Ping/pong heartbeat via WebSocket protocol

### Connection lifecycle
1. Client connects with campaign_id
2. Server sends initial state snapshot
3. Client sends commands, server processes and pushes updated state
4. On disconnect, campaign state persists (reconnectable)

## Acceptance Criteria

- **AC-01:** WebSocket endpoint accepts connections at `/game/ws/campaigns/{id}`.
- **AC-02:** Client command produces state snapshot response.
- **AC-03:** Invalid campaign_id returns error and closes connection.
- **AC-04:** Connection survives idle periods (heartbeat).
- **AC-05:** HTTP campaign routes still work alongside WebSocket.

## Files

- NEW: `engine/api/ws_campaign.py` (~150 lines)
- MODIFIED: `main.py` (mount WS router)
- NEW: `tests/test_websocket_handler.py`
