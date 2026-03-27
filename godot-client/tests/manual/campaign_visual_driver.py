from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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
SCREENSHOT_ROOT = Path(os.path.expandvars(r"%APPDATA%\Godot\app_userdata\Ember RPG\screenshots"))


TITLE_COORDS = {
    "new_game": (640, 300),
    "continue": (640, 330),
    "name_input": (640, 276),
    "adapter_dropdown": (640, 395),
    "adapter_item": {
        "fantasy_ember": (640, 423),
        "scifi_frontier": (640, 453),
    },
    "start_campaign": (640, 420),
}

GAME_COORDS = {
    "command_input": (320, 688),
}


DEFAULT_COMMANDS = [
    "look around",
    "inventory",
    "move north",
    "move east",
    "move south",
    "move west",
    "assign {player_name} to scouting",
    "defend",
    "set stockpile supplies",
    "build workshop",
    "designate harvest",
    "travel",
    "rest",
]


@dataclass
class EvidenceRecord:
    step: str
    window_screenshot: str
    viewport_screenshot: str


def wait_http(url: str, timeout: float = 25.0) -> int:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=1)
            return response.status_code
        except Exception as exc:  # pragma: no cover - manual tool
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def latest_png(folder: Path) -> Path | None:
    if not folder.exists():
        return None
    files = list(folder.glob("*.png"))
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def find_hwnd(pid: int, timeout: float = 20.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        matches: list[int] = []

        def callback(hwnd: int, _extra: object) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            _thread_id, win_pid = win32process.GetWindowThreadProcessId(hwnd)
            if win_pid == pid:
                matches.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)
        for hwnd in matches:
            if win32gui.GetClassName(hwnd) == "Engine":
                return hwnd
        time.sleep(0.25)
    raise RuntimeError(f"No Godot window found for pid={pid}")


def ensure_window_visible(hwnd: int) -> None:
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 80, 80, 1280, 720, 0)
    time.sleep(0.2)


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


def post_click(hwnd: int, x: int, y: int) -> None:
    lparam = (y << 16) | (x & 0xFFFF)
    win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)
    time.sleep(0.05)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
    time.sleep(0.05)
    win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)
    time.sleep(0.3)


def post_key(hwnd: int, vk_code: int) -> None:
    win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
    time.sleep(0.05)
    win32gui.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, 0)
    time.sleep(0.25)


def post_text(hwnd: int, text: str) -> None:
    for char in text:
        win32gui.PostMessage(hwnd, win32con.WM_CHAR, ord(char), 0)
        time.sleep(0.02)
    time.sleep(0.2)


def trigger_viewport_capture(hwnd: int, folder: str) -> str:
    folder_path = SCREENSHOT_ROOT / folder
    before = latest_png(folder_path)
    post_key(hwnd, win32con.VK_F12)
    deadline = time.time() + 5
    while time.time() < deadline:
        after = latest_png(folder_path)
        if after and after != before:
            return str(after)
        time.sleep(0.25)
    return ""


def create_campaign_ui(hwnd: int, adapter_id: str, player_name: str) -> None:
    post_click(hwnd, *TITLE_COORDS["new_game"])
    post_click(hwnd, *TITLE_COORDS["name_input"])
    post_text(hwnd, player_name)
    post_click(hwnd, *TITLE_COORDS["adapter_dropdown"])
    post_click(hwnd, *TITLE_COORDS["adapter_item"][adapter_id])
    post_click(hwnd, *TITLE_COORDS["start_campaign"])


def continue_campaign_ui(hwnd: int) -> None:
    post_click(hwnd, *TITLE_COORDS["continue"])


def focus_command_input(hwnd: int) -> None:
    post_click(hwnd, *GAME_COORDS["command_input"])


def submit_command(hwnd: int, text: str) -> None:
    focus_command_input(hwnd)
    post_text(hwnd, text)
    post_key(hwnd, win32con.VK_RETURN)


def quick_save(hwnd: int) -> None:
    post_key(hwnd, win32con.VK_F5)


def run_sequence(
    *,
    adapter_id: str,
    player_name: str,
    create_new: bool,
    commands: Iterable[str],
    wait_after_create: float,
    wait_per_command: float,
    screenshot_every: int,
) -> list[EvidenceRecord]:
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=BACKEND_CWD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    godot: subprocess.Popen[str] | None = None
    try:
        wait_http("http://127.0.0.1:8000/docs")
        godot = subprocess.Popen([str(GODOT_EXE), "--path", str(GODOT_CWD)], cwd=GODOT_CWD)
        hwnd = find_hwnd(godot.pid)
        ensure_window_visible(hwnd)
        time.sleep(2)

        evidence: list[EvidenceRecord] = []
        title_os = ROOT / "tmp" / f"{adapter_id}_title.png"
        print_window(hwnd, title_os)
        title_vp = trigger_viewport_capture(hwnd, "phase2/title")
        evidence.append(EvidenceRecord("title_screen", str(title_os), title_vp))

        if create_new:
            create_campaign_ui(hwnd, adapter_id, player_name)
        else:
            continue_campaign_ui(hwnd)
        time.sleep(wait_after_create)

        game_os = ROOT / "tmp" / f"{adapter_id}_game_boot.png"
        print_window(hwnd, game_os)
        game_vp = trigger_viewport_capture(hwnd, "phase2/game")
        evidence.append(EvidenceRecord("campaign_boot", str(game_os), game_vp))

        for index, raw_command in enumerate(commands, start=1):
            command = raw_command.format(player_name=player_name)
            submit_command(hwnd, command)
            time.sleep(wait_per_command)
            if index % screenshot_every == 0:
                step_name = f"command_{index:03d}"
                step_os = ROOT / "tmp" / f"{adapter_id}_{step_name}.png"
                print_window(hwnd, step_os)
                step_vp = trigger_viewport_capture(hwnd, "phase2/game")
                evidence.append(EvidenceRecord(step_name, str(step_os), step_vp))

        quick_save(hwnd)
        time.sleep(2)
        save_os = ROOT / "tmp" / f"{adapter_id}_quicksave.png"
        print_window(hwnd, save_os)
        save_vp = trigger_viewport_capture(hwnd, "phase2/game")
        evidence.append(EvidenceRecord("quick_save", str(save_os), save_vp))
        return evidence
    finally:
        if godot is not None:
            godot.terminate()
            try:
                godot.wait(timeout=5)
            except subprocess.TimeoutExpired:
                godot.kill()
        backend.terminate()
        try:
            backend.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend.kill()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run graphical Godot campaign QA against a live local backend.")
    parser.add_argument("--adapter", choices=["fantasy_ember", "scifi_frontier"], required=True)
    parser.add_argument("--player-name", default="VisualSmoke")
    parser.add_argument("--player-class", default="warrior")
    parser.add_argument("--continue", dest="use_continue", action="store_true")
    parser.add_argument("--wait-after-create", type=float, default=10.0)
    parser.add_argument("--wait-per-command", type=float, default=1.5)
    parser.add_argument("--screenshot-every", type=int, default=5)
    parser.add_argument("--turns", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    commands: list[str] = []
    while len(commands) < args.turns:
        commands.extend(DEFAULT_COMMANDS)
    commands = commands[: args.turns]
    evidence = run_sequence(
        adapter_id=args.adapter,
        player_name=args.player_name,
        create_new=not args.use_continue,
        commands=commands,
        wait_after_create=args.wait_after_create,
        wait_per_command=args.wait_per_command,
        screenshot_every=max(1, args.screenshot_every),
    )
    for item in evidence:
        print(f"{item.step}|{item.window_screenshot}|{item.viewport_screenshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
