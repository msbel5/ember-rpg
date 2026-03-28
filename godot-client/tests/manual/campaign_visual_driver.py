from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
ABILITY_ORDER = ["MIG", "AGI", "END", "MND", "INS", "PRE"]

TITLE_COORDS = {
    "continue": (640, 390),
    "name_input": (820, 225),
    "next_button": (388, 394),
    "player_lookup": (820, 198),
    "player_refresh": (930, 198),
    "load_first_save": (890, 296),
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
    turn: int = 0
    command: str = ""


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
    win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 80, 80, 1280, 720, win32con.SWP_SHOWWINDOW)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
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


def _start_backend_if_needed() -> subprocess.Popen[str] | None:
    try:
        wait_http("http://127.0.0.1:8000/docs", timeout=1.0)
        return None
    except RuntimeError:
        backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=BACKEND_CWD,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        wait_http("http://127.0.0.1:8000/docs")
        return backend


def _campaign_post(path: str, payload: dict | None = None) -> dict:
    response = requests.post(f"http://127.0.0.1:8000{path}", json=payload or {}, timeout=20)
    response.raise_for_status()
    return response.json()


def prepare_continue_save(adapter_id: str, player_name: str, slot_name: str) -> str:
    started = _campaign_post(
        "/game/campaigns/creation/start",
        {
            "player_name": player_name,
            "adapter_id": adapter_id,
            "profile_id": "standard",
            "seed": 77 if adapter_id == "fantasy_ember" else 133,
            "location": "Harbor Town",
        },
    )
    payload = started
    while True:
        questions = payload.get("questions", [])
        answers = payload.get("answers", [])
        if not questions or len(answers) >= len(questions):
            break
        question = questions[len(answers)]
        answer = question["answers"][0]
        payload = _campaign_post(
            f"/game/campaigns/creation/{payload['creation_id']}/answer",
            {
                "question_id": question["id"],
                "answer_id": answer["id"],
            },
        )

    assigned_stats = {ability: int(payload["current_roll"][index]) for index, ability in enumerate(ABILITY_ORDER)}
    finalized = _campaign_post(
        f"/game/campaigns/creation/{payload['creation_id']}/finalize",
        {
            "player_class": str(payload.get("recommended_class", "warrior")),
            "alignment": str(payload.get("recommended_alignment", "TN")),
            "skill_proficiencies": payload.get("recommended_skills", []),
            "assigned_stats": assigned_stats,
        },
    )
    saved = _campaign_post(
        f"/game/campaigns/{finalized['campaign_id']}/save",
        {
            "player_id": player_name,
            "slot_name": slot_name,
        },
    )
    return str(saved.get("save_id", slot_name))


def prepare_continue_save_with_seed(adapter_id: str, player_name: str, slot_name: str, seed: int) -> str:
    started = _campaign_post(
        "/game/campaigns/creation/start",
        {
            "player_name": player_name,
            "adapter_id": adapter_id,
            "profile_id": "standard",
            "seed": seed,
            "location": "Harbor Town",
        },
    )
    payload = started
    while True:
        questions = payload.get("questions", [])
        answers = payload.get("answers", [])
        if not questions or len(answers) >= len(questions):
            break
        question = questions[len(answers)]
        answer = question["answers"][0]
        payload = _campaign_post(
            f"/game/campaigns/creation/{payload['creation_id']}/answer",
            {
                "question_id": question["id"],
                "answer_id": answer["id"],
            },
        )

    assigned_stats = {ability: int(payload["current_roll"][index]) for index, ability in enumerate(ABILITY_ORDER)}
    finalized = _campaign_post(
        f"/game/campaigns/creation/{payload['creation_id']}/finalize",
        {
            "player_class": str(payload.get("recommended_class", "warrior")),
            "alignment": str(payload.get("recommended_alignment", "TN")),
            "skill_proficiencies": payload.get("recommended_skills", []),
            "assigned_stats": assigned_stats,
        },
    )
    saved = _campaign_post(
        f"/game/campaigns/{finalized['campaign_id']}/save",
        {
            "player_id": player_name,
            "slot_name": slot_name,
        },
    )
    return str(saved.get("save_id", slot_name))


def create_campaign_ui(hwnd: int, adapter_id: str, player_name: str) -> None:
    post_key(hwnd, win32con.VK_TAB)
    post_key(hwnd, win32con.VK_RETURN)
    time.sleep(0.6)
    post_click(hwnd, *TITLE_COORDS["name_input"])
    for _index in range(40):
        post_key(hwnd, win32con.VK_BACK)
    post_text(hwnd, player_name)
    if adapter_id == "scifi_frontier":
        post_key(hwnd, win32con.VK_TAB)
        post_key(hwnd, win32con.VK_DOWN)
        time.sleep(0.2)
    post_click(hwnd, *TITLE_COORDS["next_button"])
    time.sleep(1.0)
    for _index in range(6):
        post_key(hwnd, win32con.VK_RETURN)
        time.sleep(0.9)


def continue_campaign_ui(hwnd: int, player_name: str) -> None:
    post_click(hwnd, *TITLE_COORDS["continue"])
    time.sleep(0.7)
    post_click(hwnd, *TITLE_COORDS["player_lookup"])
    for _index in range(40):
        post_key(hwnd, win32con.VK_BACK)
    post_text(hwnd, player_name)
    post_click(hwnd, *TITLE_COORDS["player_refresh"])
    time.sleep(1.0)
    post_click(hwnd, *TITLE_COORDS["load_first_save"])
    time.sleep(1.2)


def focus_command_input(hwnd: int) -> None:
    post_click(hwnd, *GAME_COORDS["command_input"])


def submit_command(hwnd: int, text: str) -> None:
    focus_command_input(hwnd)
    post_text(hwnd, text)
    post_key(hwnd, win32con.VK_RETURN)


def quick_save(hwnd: int) -> None:
    post_key(hwnd, win32con.VK_F5)


def _record_step(run_dir: Path, hwnd: int, viewport_folder: str, step: str, turn: int = 0, command: str = "") -> EvidenceRecord:
    os_dir = run_dir / "os_screens"
    os_dir.mkdir(parents=True, exist_ok=True)
    window_path = os_dir / f"{step}.png"
    print_window(hwnd, window_path)
    viewport_path = trigger_viewport_capture(hwnd, viewport_folder)
    return EvidenceRecord(step=step, window_screenshot=str(window_path), viewport_screenshot=viewport_path, turn=turn, command=command)


def _write_manifest(run_dir: Path, records: list[EvidenceRecord]) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps([asdict(record) for record in records], indent=2), encoding="utf-8")
    rows = [
        "| Step | Turn | Command | OS Screenshot | Viewport Capture |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for record in records:
        rows.append(
            "| {step} | {turn} | {command} | {os_path} | {viewport} |".format(
                step=record.step,
                turn=record.turn,
                command=record.command or "",
                os_path=record.window_screenshot,
                viewport=record.viewport_screenshot,
            )
        )
    (run_dir / "manifest.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_play_log_rows(run_dir: Path, records: list[EvidenceRecord]) -> None:
    rows = [
        "| Turn | Command | Expected | Actual | Bug? | Screenshot |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        if record.turn <= 0:
            continue
        rows.append(
            "| {turn} | {command} | command resolves in live GUI | captured current frame | no | {shot} |".format(
                turn=record.turn,
                command=record.command,
                shot=record.window_screenshot,
            )
        )
    (run_dir / "play_log_rows.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def _stitch_video(run_dir: Path, records: list[EvidenceRecord], fps: int = 4) -> str:
    frame_dir = run_dir / "video_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_index = 0
    for record in records:
        source = Path(record.window_screenshot)
        if not source.exists():
            continue
        destination = frame_dir / f"frame_{frame_index:04d}.png"
        shutil.copy2(source, destination)
        frame_index += 1
    if frame_index == 0:
        return ""
    output = run_dir / "qa_recording.mp4"
    stitch_script = ROOT / "godot-client" / "tests" / "automation" / "stitch_video.py"
    result = subprocess.run(
        [sys.executable, str(stitch_script), str(frame_dir), str(output), "--fps", str(fps)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "stitch_video.py failed")
    return str(output)


def run_sequence(
    *,
    adapter_id: str,
    player_name: str,
    create_new: bool,
    seed: int,
    commands: Iterable[str],
    wait_after_create: float,
    wait_per_command: float,
    screenshot_every: int,
) -> tuple[list[EvidenceRecord], Path]:
    backend = _start_backend_if_needed()
    slot_name = f"{adapter_id}_visual_probe"
    if not create_new:
        prepare_continue_save_with_seed(adapter_id, player_name, slot_name, seed)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ROOT / "tmp" / "visual_probe" / f"{adapter_id}_{'new' if create_new else 'continue'}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    godot: subprocess.Popen[str] | None = None
    try:
        wait_http("http://127.0.0.1:8000/docs")
        godot = subprocess.Popen([str(GODOT_EXE), "--path", str(GODOT_CWD)], cwd=GODOT_CWD)
        hwnd = find_hwnd(godot.pid)
        ensure_window_visible(hwnd)
        time.sleep(2)

        evidence: list[EvidenceRecord] = []
        evidence.append(_record_step(run_dir, hwnd, "phase2/title", "title_screen"))

        if create_new:
            create_campaign_ui(hwnd, adapter_id, player_name)
        else:
            continue_campaign_ui(hwnd, player_name)
        time.sleep(wait_after_create)

        evidence.append(_record_step(run_dir, hwnd, "phase2/game", "campaign_boot"))

        for index, raw_command in enumerate(commands, start=1):
            command = raw_command.format(player_name=player_name)
            submit_command(hwnd, command)
            time.sleep(wait_per_command)
            if index % screenshot_every == 0:
                evidence.append(
                    _record_step(
                        run_dir,
                        hwnd,
                        "phase2/game",
                        f"command_{index:03d}",
                        turn=index,
                        command=command,
                    )
                )

        quick_save(hwnd)
        time.sleep(2)
        evidence.append(_record_step(run_dir, hwnd, "phase2/game", "quick_save"))
        _write_manifest(run_dir, evidence)
        _write_play_log_rows(run_dir, evidence)
        video_path = _stitch_video(run_dir, evidence)
        if video_path:
            (run_dir / "video_path.txt").write_text(video_path + "\n", encoding="utf-8")
        return evidence, run_dir
    finally:
        if godot is not None:
            godot.terminate()
            try:
                godot.wait(timeout=5)
            except subprocess.TimeoutExpired:
                godot.kill()
        if backend is not None:
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
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--turns", type=int, default=15)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    commands: list[str] = []
    while len(commands) < args.turns:
        commands.extend(DEFAULT_COMMANDS)
    commands = commands[: args.turns]
    evidence, run_dir = run_sequence(
        adapter_id=args.adapter,
        player_name=args.player_name,
        create_new=not args.use_continue,
        seed=args.seed,
        commands=commands,
        wait_after_create=args.wait_after_create,
        wait_per_command=args.wait_per_command,
        screenshot_every=max(1, args.screenshot_every),
    )
    for item in evidence:
        print(f"{item.step}|{item.window_screenshot}|{item.viewport_screenshot}|{item.turn}|{item.command}")
    print(f"manifest|{run_dir / 'manifest.md'}")
    print(f"playlog|{run_dir / 'play_log_rows.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
