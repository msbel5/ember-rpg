from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict
import json

router = APIRouter()

# Simple in-memory websocket sessions
_ws_clients: Dict[str, WebSocket] = {}

@router.websocket("/ws/game/{session_id}")
async def websocket_game(ws: WebSocket, session_id: str):
    await ws.accept()
    _ws_clients[session_id] = ws
    try:
        while True:
            data = await ws.receive_text()
            try:
                payload = json.loads(data)
            except Exception:
                await ws.send_text(json.dumps({"error": "invalid_json"}))
                continue
            # Expect {"action": "<cmd>", "payload": {...}}
            action = payload.get("action")
            body = payload.get("payload", {})
            # For now, echo to demonstrate bidirectional flow
            response = {"narrative": f"Received action {action}", "player": body}
            await ws.send_text(json.dumps(response))
    except WebSocketDisconnect:
        _ws_clients.pop(session_id, None)
