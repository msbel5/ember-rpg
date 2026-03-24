#!/usr/bin/env python3
"""Simple terminal client for Ember RPG (proof of concept).
Uses websockets to communicate with backend ws endpoint.
"""
import asyncio
import json
import sys

try:
    import curses
except Exception:
    curses = None

import websockets

WS_URL = "ws://127.0.0.1:8765/ws/game/"  # append session_id

async def run(session_id):
    uri = WS_URL + session_id
    async with websockets.connect(uri) as ws:
        print(f"Connected to {uri}")
        print("Type commands. Ctrl-C to quit.")
        while True:
            cmd = await asyncio.get_event_loop().run_in_executor(None, input, "> ")
            msg = {"action": "command", "payload": {"input": cmd}}
            await ws.send(json.dumps(msg))
            resp = await ws.recv()
            try:
                r = json.loads(resp)
                print(r.get("narrative") or r)
            except Exception:
                print(resp)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: terminal_client.py <session_id>")
        sys.exit(1)
    sid = sys.argv[1]
    asyncio.run(run(sid))
