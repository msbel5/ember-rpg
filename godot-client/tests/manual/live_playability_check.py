from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests
import win32con
import win32gui
import win32process
import win32ui
from PIL import Image


ROOT = Path(__file__).resolve().parents[3]
BACKEND_CWD = ROOT / "frp-backend"
GODOT_CWD = ROOT / "godot-client"
GODOT_EXE = Path(r"C:\Tools\Scoop\apps\godot\current\godot.exe")
PROFILE_PATH = Path(os.path.expandvars(r"%APPDATA%\Godot\app_userdata\Ember RPG\client_profile.cfg"))

AUTOMATION_COMMAND_ENV = "EMBER_AUTOMATION_COMMAND_FILE"
AUTOMATION_RESULT_ENV = "EMBER_AUTOMATION_RESULT_FILE"
AUTOMATION_STATUS_ENV = "EMBER_AUTOMATION_STATUS_FILE"
AUTOMATION_ARTIFACT_ENV = "EMBER_AUTOMATION_ARTIFACT_ROOT"
BACKEND_ENV = "EMBER_RPG_BACKEND_URL"

TITLE_CONTINUE_PATH = "TitleMenu/FrontDoor/RootSplit/MenuColumn/MenuPanel/MenuMargin/MenuVBox/ContinueButton"
WORLD_VIEW_PATH = "MainMargin/MainVBox/ContentSplit/WorldPane/WorldViewportContainer"
DIALOG_CLOSE_PATH = "MainMargin/MainVBox/ContentSplit/WorldPane/DialogOverlay/DialogVBox/CloseButton"
MAP_BUTTON_PATH = "MainMargin/MainVBox/InstrumentRail/RailMargin/RailVBox/ShellGrid/MapButton"
QUICKSAVE_BUTTON_PATH = "MainMargin/MainVBox/InstrumentRail/RailMargin/RailVBox/IntelRow/StateFrame/StateMargin/StateVBox/SaveRow/QuickSaveButton"
MAP_ROUTE_BUTTON_PATH = "MainMargin/MainVBox/ContentSplit/ModalHost/ModalStack/MinimapPanel/MinimapMargin/MinimapVBox/RoutesList/RouteButton0"

BLOCKED_TILES = {"wall", "water", "void"}


def wait_http(url: str, timeout: float = 25.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            requests.get(url, timeout=1).raise_for_status()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.4)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def ensure_backend() -> subprocess.Popen[str] | None:
    try:
        wait_http("http://127.0.0.1:8741/docs", timeout=1.5)
        return None
    except RuntimeError:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8741"],
            cwd=BACKEND_CWD,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        wait_http("http://127.0.0.1:8741/docs", timeout=25.0)
        return process


def json_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(f"http://127.0.0.1:8741{path}", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def prepare_continue_save(player_name: str, adapter_id: str, slot_name: str) -> str:
    campaign = json_post(
        "/game/campaigns",
        {
            "player_name": player_name,
            "player_class": "warrior",
            "adapter_id": adapter_id,
            "profile_id": "standard",
            "seed": 4242,
        },
    )
    campaign_id = str(campaign.get("campaign_id", "")).strip()
    if not campaign_id:
        raise RuntimeError("Campaign creation did not return campaign_id.")
    save = json_post(
        f"/game/campaigns/{campaign_id}/save",
        {
            "player_id": player_name,
            "slot_name": slot_name,
        },
    )
    save_id = str(save.get("save_id", slot_name)).strip()
    if not save_id:
        raise RuntimeError("Save creation did not return save_id.")
    return save_id


def seed_profile(player_name: str, adapter_id: str, save_id: str) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(
        "\n".join(
            [
                "[profile]",
                f'last_player_id="{player_name}"',
                f'last_resume_player_id="{player_name}"',
                f'last_adapter_id="{adapter_id}"',
                f'last_campaign_save_id="{save_id}"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def find_hwnd(pid: int, timeout: float = 20.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        matches: list[int] = []

        def callback(hwnd: int, _extra: object) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _, win_pid = win32process.GetWindowThreadProcessId(hwnd)
            if win_pid == pid:
                matches.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)
        if matches:
            return matches[0]
        time.sleep(0.25)
    raise RuntimeError(f"No Godot window found for pid={pid}")


def ensure_window_visible(hwnd: int) -> None:
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 80, 80, 1600, 900, 0)
    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 80, 80, 1600, 900, win32con.SWP_SHOWWINDOW)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.25)


def print_window(hwnd: int, destination: Path) -> None:
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width = right - left
    height = bottom - top
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
    save_dc.SelectObject(bitmap)
    try:
        import ctypes

        ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 3)
        bitmap_info = bitmap.GetInfo()
        bitmap_bits = bitmap.GetBitmapBits(True)
        image = Image.frombuffer(
            "RGB",
            (bitmap_info["bmWidth"], bitmap_info["bmHeight"]),
            bitmap_bits,
            "raw",
            "BGRX",
            0,
            1,
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        image.save(destination)
    finally:
        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)


class BridgeClient:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.bridge_dir = run_dir / "bridge"
        self.command_path = self.bridge_dir / "command.json"
        self.result_path = self.bridge_dir / "result.json"
        self.status_path = self.bridge_dir / "status.json"
        self.sequence = 0
        self.process: subprocess.Popen[str] | None = None
        self.hwnd: int | None = None

    def launch(self) -> None:
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.command_path, self.result_path, self.status_path):
            if path.exists():
                path.unlink()
        self.process = subprocess.Popen(
            [str(GODOT_EXE), "--path", str(GODOT_CWD)],
            cwd=GODOT_CWD,
            env={
                **os.environ,
                BACKEND_ENV: "http://127.0.0.1:8741",
                AUTOMATION_COMMAND_ENV: str(self.command_path),
                AUTOMATION_RESULT_ENV: str(self.result_path),
                AUTOMATION_STATUS_ENV: str(self.status_path),
                AUTOMATION_ARTIFACT_ENV: str(self.run_dir),
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        time.sleep(6.0)
        if self.process.poll() is not None:
            raise RuntimeError("Godot exited before automation bridge attached.")
        self.hwnd = find_hwnd(self.process.pid)
        ensure_window_visible(self.hwnd)
        self.wait_for_status_ready()

    def close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def wait_for_status_ready(self, timeout: float = 20.0) -> None:
        self.wait_for(
            lambda: self.status_path.exists() and _read_json(self.status_path).get("ready") is True,
            timeout=timeout,
            description="runtime automation bridge ready",
        )

    def send(self, action: str, **payload: Any) -> dict[str, Any]:
        self.sequence += 1
        command = {"seq": self.sequence, "action": action, **payload}
        self.command_path.write_text(json.dumps(command), encoding="utf-8")
        deadline = time.time() + 15.0
        while time.time() < deadline:
            result = _read_json(self.result_path)
            if int(result.get("seq", -1)) != self.sequence:
                time.sleep(0.1)
                continue
            if str(result.get("status", "ok")) == "error":
                raise RuntimeError(str(result.get("message", "Bridge command failed.")))
            return result
        raise RuntimeError(f"Timed out waiting for bridge result for action {action}")

    def activate_node(self, node_path: str) -> None:
        self.send("activate_node", node_path=node_path)

    def query_state(self) -> dict[str, Any]:
        return self.send("query_runtime_state")

    def query_node(self, node_path: str) -> dict[str, Any]:
        return self.send("query_state", node_path=node_path)

    def capture_viewport(self, tag: str) -> str:
        return str(self.send("capture_viewport", tag=tag).get("path", ""))

    def click_tile(self, tile_x: int, tile_y: int, button: str) -> None:
        self.send("world_tile_click", tile_x=tile_x, tile_y=tile_y, button=button, node_path=WORLD_VIEW_PATH)

    def wait_for(self, predicate: Callable[[], bool], timeout: float, description: str) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if predicate():
                return
            time.sleep(0.2)
        raise RuntimeError(f"Timed out waiting for {description}")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def choose_walk_tile(runtime_state: dict[str, Any]) -> tuple[int, int]:
    neighbors = runtime_state.get("neighbor_tiles", [])
    for entry in neighbors:
        if not isinstance(entry, dict):
            continue
        if bool(entry.get("occupied", False)):
            continue
        tile_name = str(entry.get("tile_name", "")).strip().lower()
        if tile_name in BLOCKED_TILES:
            continue
        tile = entry.get("tile", [])
        if isinstance(tile, list) and len(tile) >= 2:
            return int(tile[0]), int(tile[1])
    raise RuntimeError("No adjacent walkable tile found in runtime state.")


def choose_nearest_npc(runtime_state: dict[str, Any]) -> tuple[int, int]:
    player_tile = runtime_state.get("player_tile", [0, 0])
    px, py = int(player_tile[0]), int(player_tile[1])
    npcs: list[tuple[int, int, int]] = []
    for entity in runtime_state.get("entities", []):
        if not isinstance(entity, dict) or str(entity.get("bucket", "")) != "npcs":
            continue
        pos = entity.get("position", [])
        if not isinstance(pos, list) or len(pos) < 2:
            continue
        ex, ey = int(pos[0]), int(pos[1])
        dist = abs(ex - px) + abs(ey - py)
        npcs.append((dist, ex, ey))
    if not npcs:
        raise RuntimeError("No NPCs available in runtime state.")
    npcs.sort()
    _, ex, ey = npcs[0]
    return ex, ey


def main() -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "tmp" / "live_playability" / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    player_name = "GatePilot"
    adapter_id = "fantasy_ember"
    slot_name = "live_playability"

    backend_process = ensure_backend()
    client = BridgeClient(run_dir)
    manifest: dict[str, Any] = {"run_dir": str(run_dir), "steps": []}

    try:
        save_id = prepare_continue_save(player_name, adapter_id, slot_name)
        seed_profile(player_name, adapter_id, save_id)
        client.launch()

        title_os = run_dir / "title_os.png"
        print_window(client.hwnd, title_os)  # type: ignore[arg-type]
        title_viewport = client.capture_viewport("title_frontdoor")
        manifest["steps"].append({"step": "title", "os": str(title_os), "viewport": title_viewport})

        client.activate_node(TITLE_CONTINUE_PATH)
        client.wait_for(lambda: client.send("query_state").get("scene_name", "") == "GameSession", 20.0, "GameSession")

        boot_state = client.query_state()
        if str(boot_state.get("shell_mode", "")) != "exploration":
            raise RuntimeError(f"Expected exploration on boot, got {boot_state.get('shell_mode')}")
        if bool(boot_state.get("dialog_active", False)):
            raise RuntimeError("Dialog was active on world spawn.")

        boot_os = run_dir / "boot_os.png"
        print_window(client.hwnd, boot_os)  # type: ignore[arg-type]
        boot_viewport = client.capture_viewport("boot_world")
        manifest["steps"].append({"step": "boot", "os": str(boot_os), "viewport": boot_viewport, "state": boot_state})

        start_tile = tuple(int(value) for value in boot_state.get("player_tile", [0, 0]))
        move_x, move_y = choose_walk_tile(boot_state)
        client.click_tile(move_x, move_y, "right")
        client.wait_for(
            lambda: tuple(int(value) for value in client.query_state().get("player_tile", [0, 0])) != start_tile,
            12.0,
            "player movement",
        )

        moved_state = client.query_state()
        moved_os = run_dir / "moved_os.png"
        print_window(client.hwnd, moved_os)  # type: ignore[arg-type]
        moved_viewport = client.capture_viewport("moved_world")
        manifest["steps"].append({"step": "move", "os": str(moved_os), "viewport": moved_viewport, "state": moved_state})

        npc_x, npc_y = choose_nearest_npc(moved_state)
        client.click_tile(npc_x, npc_y, "left")
        client.wait_for(lambda: bool(client.query_state().get("dialog_active", False)), 15.0, "dialog open")

        dialog_state = client.query_state()
        dialog_os = run_dir / "dialog_os.png"
        print_window(client.hwnd, dialog_os)  # type: ignore[arg-type]
        dialog_viewport = client.capture_viewport("dialog_open")
        manifest["steps"].append({"step": "dialog", "os": str(dialog_os), "viewport": dialog_viewport, "state": dialog_state})

        if int(dialog_state.get("ask_about_topic_count", 0)) > 0:
            manifest["steps"].append({"step": "ask_about_available", "count": int(dialog_state.get("ask_about_topic_count", 0))})

        client.activate_node(DIALOG_CLOSE_PATH)
        client.wait_for(lambda: not bool(client.query_state().get("dialog_active", False)), 8.0, "dialog close")

        client.activate_node(MAP_BUTTON_PATH)
        client.wait_for(lambda: str(client.query_state().get("active_panel_id", "")) == "map", 8.0, "map panel")
        map_os = run_dir / "map_os.png"
        print_window(client.hwnd, map_os)  # type: ignore[arg-type]
        map_viewport = client.capture_viewport("map_panel")
        manifest["steps"].append({"step": "map", "os": str(map_os), "viewport": map_viewport})

        route_probe = client.query_node(MAP_ROUTE_BUTTON_PATH)
        if bool(route_probe.get("node_exists", False)) and bool(route_probe.get("node_visible", False)):
            client.activate_node(MAP_ROUTE_BUTTON_PATH)
            client.wait_for(lambda: bool(client.query_state().get("travel_active", False)), 10.0, "travel start")
            travel_state = client.query_state()
            travel_os = run_dir / "travel_os.png"
            print_window(client.hwnd, travel_os)  # type: ignore[arg-type]
            travel_viewport = client.capture_viewport("travel_active")
            manifest["steps"].append({"step": "travel", "os": str(travel_os), "viewport": travel_viewport, "state": travel_state})

        client.activate_node(MAP_BUTTON_PATH)
        client.wait_for(lambda: str(client.query_state().get("active_panel_id", "")) == "", 6.0, "map panel close")

        client.activate_node(QUICKSAVE_BUTTON_PATH)
        time.sleep(1.0)
        save_os = run_dir / "save_os.png"
        print_window(client.hwnd, save_os)  # type: ignore[arg-type]
        save_viewport = client.capture_viewport("quick_save")
        manifest["steps"].append({"step": "quick_save", "os": str(save_os), "viewport": save_viewport})

        client.close()
        client = BridgeClient(run_dir)
        client.launch()
        client.activate_node(TITLE_CONTINUE_PATH)
        client.wait_for(lambda: client.send("query_state").get("scene_name", "") == "GameSession", 20.0, "continued GameSession")
        reload_state = client.query_state()
        if str(reload_state.get("shell_mode", "")) != "exploration":
            raise RuntimeError(f"Expected exploration after continue, got {reload_state.get('shell_mode')}")
        if bool(reload_state.get("dialog_active", False)):
            raise RuntimeError("Dialog was active after continue load.")
        reload_os = run_dir / "reload_os.png"
        print_window(client.hwnd, reload_os)  # type: ignore[arg-type]
        reload_viewport = client.capture_viewport("reload_world")
        manifest["steps"].append({"step": "reload", "os": str(reload_os), "viewport": reload_viewport, "state": reload_state})

        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(str(run_dir))
        return 0
    finally:
        client.close()
        if backend_process is not None and backend_process.poll() is None:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                backend_process.kill()


if __name__ == "__main__":
    raise SystemExit(main())



