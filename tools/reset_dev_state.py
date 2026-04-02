"""Reset local Ember RPG runtime state for clean Godot/manual proof runs."""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SAVE_ROOT = REPO_ROOT / "frp-backend" / "saves"
VISUAL_AUTOMATION_ROOT = REPO_ROOT / "tmp" / "visual_automation"


def godot_user_data_root(appdata: str | None = None) -> Path | None:
    resolved = (appdata or os.environ.get("APPDATA", "")).strip()
    if not resolved:
        return None
    return Path(resolved) / "Godot" / "app_userdata" / "Ember RPG"


def screenshot_cache_root(appdata: str | None = None) -> Path | None:
    user_root = godot_user_data_root(appdata)
    return None if user_root is None else user_root / "screenshots"


def client_profile_path(appdata: str | None = None) -> Path | None:
    user_root = godot_user_data_root(appdata)
    return None if user_root is None else user_root / "client_profile.cfg"


def _clear_directory(path: Path) -> list[str]:
    removed: list[str] = []
    if not path.exists():
        return removed
    for child in path.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink()
        except FileNotFoundError:
            continue
        removed.append(str(child))
    return removed


def reset_dev_state(*, repo_root: Path | None = None, appdata: str | None = None) -> dict[str, list[str]]:
    root = repo_root or REPO_ROOT
    removed = {
        "saves": _clear_directory(root / "frp-backend" / "saves"),
        "visual_automation": _clear_directory(root / "tmp" / "visual_automation"),
        "screenshots": [],
        "profile": [],
    }

    screenshots = screenshot_cache_root(appdata)
    if screenshots is not None:
        removed["screenshots"] = _clear_directory(screenshots)

    profile = client_profile_path(appdata)
    if profile is not None and profile.exists():
        try:
            profile.unlink()
            removed["profile"].append(str(profile))
        except FileNotFoundError:
            pass

    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset local Ember RPG runtime state.")
    parser.add_argument("--appdata", default="", help="Override %%APPDATA%% for testing.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    removed = reset_dev_state(appdata=args.appdata or None)
    total = sum(len(values) for values in removed.values())
    print(f"Reset Ember RPG local runtime state. Removed {total} artifact(s).")
    for group, values in removed.items():
        print(f"{group}: {len(values)}")


if __name__ == "__main__":
    main()
