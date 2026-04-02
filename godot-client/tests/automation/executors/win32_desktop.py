from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
import importlib.util

from automation.artifacts import ArtifactManager
from automation.executors.base import AutomationExecutor, CapabilityUnavailableError
from automation.models import ArtifactRecord, AutomationScenario
from automation.process_utils import (
    build_backend_url,
    find_available_port,
    is_port_available,
    read_json,
    terminate_process,
    wait_backend_contract,
    wait_for_json,
    write_json_atomic,
)

try:  # pragma: no cover - import availability depends on host setup
    import win32con
    import win32gui
    import win32process
    import win32ui
    from PIL import Image

    WIN32_AVAILABLE = True
except Exception:  # pragma: no cover - exercised by import fallback tests
    win32con = None
    win32gui = None
    win32process = None
    win32ui = None
    Image = None
    WIN32_AVAILABLE = False


SCREENSHOT_ROOT = Path(os.path.expandvars(r"%APPDATA%\Godot\app_userdata\Ember RPG\screenshots"))
BACKEND_ENV = "EMBER_RPG_BACKEND_URL"
AUTOMATION_COMMAND_ENV = "EMBER_AUTOMATION_COMMAND_FILE"
AUTOMATION_RESULT_ENV = "EMBER_AUTOMATION_RESULT_FILE"
AUTOMATION_STATUS_ENV = "EMBER_AUTOMATION_STATUS_FILE"
AUTOMATION_ARTIFACT_ENV = "EMBER_AUTOMATION_ARTIFACT_ROOT"
DESKTOP_REQUIREMENTS = {
    "pywin32": ("win32gui", "Install desktop automation support with `pip install -r godot-client/tests/automation/requirements-desktop.txt`."),
    "Pillow": ("PIL", "Install image capture support with `pip install -r godot-client/tests/automation/requirements-desktop.txt`."),
    "requests": ("requests", "Install the shared automation HTTP dependency with `pip install -r godot-client/tests/automation/requirements-desktop.txt`."),
}

KEY_NAME_TO_VK = {
    "backspace": 0x08,
    "enter": 0x0D,
    "tab": 0x09,
    "escape": 0x1B,
    "esc": 0x1B,
    "space": 0x20,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "home": 0x24,
    "f5": 0x74,
    "f9": 0x78,
    "f12": 0x7B,
}

BUTTON_DOWN = {"left": 0x0201, "right": 0x0204, "middle": 0x0207}
BUTTON_UP = {"left": 0x0202, "right": 0x0205, "middle": 0x0208}
BUTTON_MASK = {"left": 0x0001, "right": 0x0002, "middle": 0x0010}


class Win32DesktopExecutor(AutomationExecutor):
    name = "win32_desktop"

    def __init__(self, scenario: AutomationScenario, artifacts: ArtifactManager):
        super().__init__(scenario, artifacts)
        self._backend_process: subprocess.Popen[str] | None = None
        self._client_process: subprocess.Popen[str] | None = None
        self._backend_started_here = False
        self._hwnd: int | None = None
        self._cursor = (0, 0)
        self._sequence = 0
        self._bridge_dir = self.artifacts.run_dir / "bridge"
        self._command_path = self._bridge_dir / "command.json"
        self._result_path = self._bridge_dir / "result.json"
        self._status_path = self._bridge_dir / "status.json"

    @property
    def capabilities(self) -> set[str]:
        capabilities = {"keyboard", "mouse", "viewport_capture", "issue_reporting"}
        if WIN32_AVAILABLE:
            capabilities.update({"os_capture", "window_activation", "semantic_controls"})
        return capabilities

    def environment_health(self) -> dict:
        missing: list[str] = []
        notes: list[str] = []
        for package_name, (module_name, remediation) in DESKTOP_REQUIREMENTS.items():
            if importlib.util.find_spec(module_name) is None:
                missing.append(package_name)
                notes.append(f"Missing `{package_name}`. {remediation}")
        if WIN32_AVAILABLE and "pywin32" in missing:
            missing.remove("pywin32")
        if not WIN32_AVAILABLE and "pywin32" not in missing:
            missing.insert(0, "pywin32")
            notes.insert(0, "Missing `pywin32`. Install desktop automation support with `pip install -r godot-client/tests/automation/requirements-desktop.txt`.")
        summary = ""
        if missing:
            summary = "Desktop automation environment is incomplete: %s." % ", ".join(missing)
        return {
            "ok": not missing,
            "summary": summary,
            "notes": notes,
            "missing": missing,
        }

    def launch_backend(self) -> None:
        port = self.backend_port
        if not is_port_available(self.backend_host, port):
            port = find_available_port(self.backend_host, max(port + 1, 8765))
        self.backend_port = port
        self.backend_url = build_backend_url(self.backend_host, port, self.backend_url)
        self._backend_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                self.backend_host,
                "--port",
                str(self.backend_port),
            ],
            cwd=self.scenario.backend_cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._backend_started_here = True
        wait_backend_contract(self.backend_url, timeout=25.0)

    def stop_backend(self) -> None:
        if self._backend_started_here:
            terminate_process(self._backend_process)
        self._backend_process = None
        self._backend_started_here = False

    def launch_client(self) -> None:
        self._require_win32("launch_client", "Win32 desktop automation dependencies are not available.")
        self._bridge_dir.mkdir(parents=True, exist_ok=True)
        for path in (self._command_path, self._result_path, self._status_path):
            if path.exists():
                path.unlink()
        args = [self.scenario.godot_executable, "--path", self.scenario.godot_project_dir]
        self._client_process = subprocess.Popen(
            args,
            cwd=self.scenario.godot_project_dir,
            env={
                **os.environ,
                BACKEND_ENV: self.backend_url,
                AUTOMATION_COMMAND_ENV: str(self._command_path),
                AUTOMATION_RESULT_ENV: str(self._result_path),
                AUTOMATION_STATUS_ENV: str(self._status_path),
                AUTOMATION_ARTIFACT_ENV: str(self.artifacts.run_dir),
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        time.sleep(max(self.scenario.start_wait_ms, 0) / 1000.0)
        if self._client_process.poll() is not None:
            raise RuntimeError("Godot client exited before the desktop executor could attach.")
        self._hwnd = self._find_hwnd(self._client_process.pid)
        self.activate_window()
        status = wait_for_json(self._status_path, lambda payload: payload.get("ready") is True, timeout=20.0)
        if str(status.get("status", "")) == "error":
            raise RuntimeError(str(status.get("message", "Runtime automation bridge failed to launch.")))

    def close_client(self) -> None:
        terminate_process(self._client_process)
        self._client_process = None
        self._hwnd = None

    def activate_window(self) -> None:
        self._require_win32("activate_window", "Window activation requires Win32 automation support.")
        hwnd = self._require_hwnd()
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 80, 80, 1600, 900, 0)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_NOTOPMOST,
            80,
            80,
            1600,
            900,
            win32con.SWP_SHOWWINDOW,
        )
        try:  # pragma: no cover - host policy may reject foreground changes
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        time.sleep(0.2)

    def move_cursor(self, x: int, y: int) -> None:
        hwnd = self._require_hwnd()
        self._cursor = (x, y)
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, self._lparam(x, y))
        time.sleep(0.05)

    def mouse_down(self, button: str = "left") -> None:
        hwnd = self._require_hwnd()
        x, y = self._cursor
        normalized = self._normalize_button(button)
        win32gui.PostMessage(
            hwnd,
            BUTTON_DOWN[normalized],
            BUTTON_MASK[normalized],
            self._lparam(x, y),
        )
        time.sleep(0.05)

    def mouse_up(self, button: str = "left") -> None:
        hwnd = self._require_hwnd()
        x, y = self._cursor
        normalized = self._normalize_button(button)
        win32gui.PostMessage(hwnd, BUTTON_UP[normalized], 0, self._lparam(x, y))
        time.sleep(0.05)

    def mouse_click(self, x: int, y: int, button: str = "left") -> None:
        self.move_cursor(x, y)
        self.mouse_down(button)
        self.mouse_up(button)
        time.sleep(0.2)

    def key_down(self, key: str) -> None:
        hwnd = self._require_hwnd()
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, self._vk_for_key(key), 0)
        time.sleep(0.05)

    def key_up(self, key: str) -> None:
        hwnd = self._require_hwnd()
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, self._vk_for_key(key), 0)
        time.sleep(0.05)

    def type_text(self, text: str) -> None:
        hwnd = self._require_hwnd()
        for char in text:
            win32gui.PostMessage(hwnd, win32con.WM_CHAR, ord(char), 0)
            time.sleep(0.02)
        time.sleep(0.1)

    def capture_os(self, tag: str) -> ArtifactRecord:
        self._require_win32("capture_os", "OS/window screenshots require Win32 automation support.")
        hwnd = self._require_hwnd()
        destination = self.artifacts.artifact_path("os_screens", tag, ".png")
        self._print_window(hwnd, destination)
        return self.artifacts.register(tag, "os_screenshot", destination)

    def capture_viewport(self, tag: str) -> ArtifactRecord:
        if self._status_path.exists():
            response = self._send_command("capture_viewport", tag=tag)
            source_path = Path(str(response.get("path", "")))
            if not source_path.exists():
                raise RuntimeError(f"Runtime automation bridge reported a missing viewport artifact: {source_path}")
            scene_name = str(response.get("scene_name", "")).strip()
            note = scene_name
            destination = self.artifacts.artifact_path("viewport_captures", tag, ".png")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            return self.artifacts.register(tag, "viewport_capture", destination, note=note)
        baseline = self._latest_png()
        self.key_press("f12")
        captured_path = self._wait_for_viewport_capture(baseline)
        destination = self.artifacts.artifact_path("viewport_captures", tag, ".png")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(captured_path, destination)
        return self.artifacts.register(tag, "viewport_capture", destination, note=str(captured_path))

    def focus_node(self, node_path: str) -> None:
        self._send_command("focus_node", node_path=node_path)

    def activate_node(self, node_path: str) -> None:
        self._send_command("activate_node", node_path=node_path)

    def set_text_node(self, node_path: str, text: str) -> None:
        self._send_command("set_text_node", node_path=node_path, text=text)

    def select_option_node(self, node_path: str, option_text: str) -> None:
        self._send_command("select_option_node", node_path=node_path, option_text=option_text)

    def click_node(
        self,
        node_path: str,
        *,
        normalized_x: float = 0.5,
        normalized_y: float = 0.5,
        button: str = "left",
    ) -> None:
        self._send_command(
            "click_node",
            node_path=node_path,
            normalized_x=normalized_x,
            normalized_y=normalized_y,
            button=button,
        )

    def current_scene_name(self) -> str:
        response = self.query_node_state()
        return str(response.get("scene_name", "")).strip()

    def node_exists(self, node_path: str) -> bool:
        response = self.query_node_state(node_path)
        return bool(response.get("node_exists", False))

    def query_node_state(self, node_path: str | None = None) -> dict:
        payload = {}
        if node_path:
            payload["node_path"] = node_path
        return self._send_command("query_state", **payload)

    def bridge_status(self) -> dict:
        return read_json(self._status_path)

    def _docs_url(self) -> str:
        return f"{self.backend_url.rstrip('/')}/docs"

    def _send_command(self, action: str, **payload) -> dict:
        if self._client_process is None or self._client_process.poll() is not None:
            raise RuntimeError("Windowed Godot runtime bridge is not running.")
        self._sequence += 1
        command = {"seq": self._sequence, "action": action, **payload}
        write_json_atomic(self._command_path, command)
        result = wait_for_json(
            self._result_path,
            lambda entry: int(entry.get("seq", -1)) == self._sequence,
            timeout=15.0,
        )
        status = str(result.get("status", "ok"))
        if status == "gap":
            raise CapabilityUnavailableError(str(result.get("message", "Executor capability gap.")))
        if status == "error":
            raise RuntimeError(str(result.get("message", "Runtime automation bridge command failed.")))
        return result

    def _require_win32(self, capability: str, message: str) -> None:
        if not WIN32_AVAILABLE:
            raise CapabilityUnavailableError(f"{message} Missing support for `{capability}`.")

    def _require_hwnd(self) -> int:
        self._require_win32("window_handle", "Desktop input forwarding requires Win32 automation support.")
        if self._hwnd is None:
            raise RuntimeError("Godot desktop window is not attached.")
        return self._hwnd

    def _find_hwnd(self, pid: int, timeout: float = 20.0) -> int:
        self._require_win32("find_hwnd", "Desktop window lookup requires Win32 automation support.")
        deadline = time.time() + timeout
        matches: list[int] = []
        while time.time() < deadline:
            matches.clear()

            def callback(hwnd: int, _extra: object) -> bool:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                _thread_id, win_pid = win32process.GetWindowThreadProcessId(hwnd)
                if win_pid == pid:
                    matches.append(hwnd)
                return True

            win32gui.EnumWindows(callback, None)
            if matches:
                return matches[0]
            time.sleep(0.25)
        raise RuntimeError(f"No Godot window found for pid={pid}")

    def _vk_for_key(self, key: str) -> int:
        normalized = key.strip().lower()
        if not normalized:
            raise ValueError("Key value cannot be empty.")
        if normalized in KEY_NAME_TO_VK:
            return KEY_NAME_TO_VK[normalized]
        if len(normalized) == 1:
            return ord(normalized.upper())
        raise ValueError(f"Unsupported key mapping `{key}`.")

    def _normalize_button(self, button: str) -> str:
        normalized = button.strip().lower()
        if normalized not in BUTTON_DOWN:
            raise ValueError(f"Unsupported mouse button `{button}`.")
        return normalized

    def _lparam(self, x: int, y: int) -> int:
        return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

    def _print_window(self, hwnd: int, destination: Path) -> None:
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

    def _wait_for_viewport_capture(self, baseline: Path | None, timeout: float = 5.0) -> Path:
        deadline = time.time() + timeout
        baseline_marker = self._capture_marker(baseline)
        while time.time() < deadline:
            newest = self._latest_png()
            newest_marker = self._capture_marker(newest)
            if newest is not None and newest_marker != baseline_marker:
                return newest
            time.sleep(0.1)
        raise RuntimeError("Timed out waiting for a viewport capture after F12.")

    def _latest_png(self) -> Path | None:
        if not SCREENSHOT_ROOT.exists():
            return None
        files = list(SCREENSHOT_ROOT.rglob("*.png"))
        if not files:
            return None
        return max(files, key=lambda path: path.stat().st_mtime)

    def _capture_marker(self, path: Path | None) -> tuple[str, int, int] | None:
        if path is None or not path.exists():
            return None
        stats = path.stat()
        return (str(path), stats.st_mtime_ns, stats.st_size)
