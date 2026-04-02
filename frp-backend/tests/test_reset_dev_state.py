from __future__ import annotations

from pathlib import Path

from tools.reset_dev_state import reset_dev_state


def test_reset_dev_state_clears_saves_visual_artifacts_and_profile(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    saves = repo_root / "frp-backend" / "saves"
    visual = repo_root / "tmp" / "visual_automation" / "old_run"
    saves.mkdir(parents=True)
    visual.mkdir(parents=True)
    (saves / "autosave_1.json").write_text("{}", encoding="utf-8")
    (visual / "artifact.txt").write_text("x", encoding="utf-8")

    appdata = tmp_path / "appdata"
    screenshots = appdata / "Godot" / "app_userdata" / "Ember RPG" / "screenshots" / "set_1"
    screenshots.mkdir(parents=True)
    (screenshots / "capture.png").write_text("img", encoding="utf-8")
    profile = appdata / "Godot" / "app_userdata" / "Ember RPG" / "client_profile.cfg"
    profile.write_text("[profile]\nlast_player_id=\"Chaos\"\n", encoding="utf-8")

    removed = reset_dev_state(repo_root=repo_root, appdata=str(appdata))

    assert removed["saves"]
    assert removed["visual_automation"]
    assert removed["screenshots"]
    assert removed["profile"] == [str(profile)]
    assert list(saves.iterdir()) == []
    assert list((repo_root / "tmp" / "visual_automation").iterdir()) == []
    assert not profile.exists()
    assert list((appdata / "Godot" / "app_userdata" / "Ember RPG" / "screenshots").iterdir()) == []


def test_reset_dev_state_is_idempotent_when_profile_is_already_gone(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "frp-backend" / "saves").mkdir(parents=True)
    (repo_root / "tmp" / "visual_automation").mkdir(parents=True)

    appdata = tmp_path / "appdata"
    profile_dir = appdata / "Godot" / "app_userdata" / "Ember RPG"
    profile_dir.mkdir(parents=True)
    profile = profile_dir / "client_profile.cfg"
    profile.write_text("[profile]\nlast_player_id=\"Chaos\"\n", encoding="utf-8")

    first = reset_dev_state(repo_root=repo_root, appdata=str(appdata))
    second = reset_dev_state(repo_root=repo_root, appdata=str(appdata))

    assert first["profile"] == [str(profile)]
    assert second["profile"] == []
