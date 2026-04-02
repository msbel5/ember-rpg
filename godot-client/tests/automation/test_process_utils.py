from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError

from automation.process_utils import (
    backend_supports_paths,
    build_backend_url,
    fetch_backend_health,
    wait_backend_contract,
    write_json_atomic,
)


def test_write_json_atomic_falls_back_to_direct_overwrite_on_windows_lock(
    tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "command.json"
    target.write_text("{}", encoding="utf-8")

    def always_locked(self: Path, destination: Path) -> Path:
        raise PermissionError("locked")

    monkeypatch.setattr(Path, "replace", always_locked)
    monkeypatch.setattr("automation.process_utils.time.sleep", lambda _seconds: None)

    payload = {"seq": 7, "action": "mouse_click", "x": 42, "y": 18}
    write_json_atomic(target, payload)

    assert json.loads(target.read_text(encoding="utf-8")) == payload
    assert not target.with_suffix(".json.tmp").exists()


def test_backend_supports_paths_requires_campaign_contract(monkeypatch) -> None:
    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "paths": {
                        "/game/campaigns": {},
                        "/game/campaigns/creation/catalog": {},
                        "/game/campaigns/load/{save_id}": {},
                    }
                }
            ).encode("utf-8")

    monkeypatch.setattr("automation.process_utils.urlopen", lambda *_args, **_kwargs: _Response())

    assert backend_supports_paths("http://127.0.0.1:8741") is True


def test_fetch_backend_health_reads_campaign_client_contract(monkeypatch) -> None:
    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "ok": True,
                    "campaign_creation": True,
                    "campaign_runtime": True,
                    "campaign_save_load": True,
                    "schema_version": "campaign-v2",
                }
            ).encode("utf-8")

    monkeypatch.setattr("automation.process_utils.urlopen", lambda *_args, **_kwargs: _Response())

    assert fetch_backend_health("http://127.0.0.1:8741") == {
        "ok": True,
        "campaign_creation": True,
        "campaign_runtime": True,
        "campaign_save_load": True,
        "schema_version": "campaign-v2",
    }


def test_backend_supports_paths_rejects_session_only_backend(monkeypatch) -> None:
    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps({"paths": {"/game/session/new": {}, "/game/saves/{player_id}": {}}}).encode("utf-8")

    monkeypatch.setattr("automation.process_utils.urlopen", lambda *_args, **_kwargs: _Response())

    assert backend_supports_paths("http://127.0.0.1:8741") is False


def test_wait_backend_contract_retries_until_paths_exist(monkeypatch) -> None:
    attempts = {"count": 0}

    class _Response:
        status = 200

        def __init__(self, payload: dict):
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(self._payload).encode("utf-8")

    def fake_urlopen(*_args, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise HTTPError("http://127.0.0.1:8741/openapi.json", 404, "not found", {}, None)
        return _Response(
            {
                "paths": {
                    "/game/campaigns": {},
                    "/game/campaigns/creation/catalog": {},
                    "/game/campaigns/load/{save_id}": {},
                }
            }
        )

    monkeypatch.setattr("automation.process_utils.urlopen", fake_urlopen)
    monkeypatch.setattr("automation.process_utils.time.sleep", lambda _seconds: None)

    wait_backend_contract("http://127.0.0.1:8741", timeout=0.2)

    assert attempts["count"] == 2


def test_build_backend_url_preserves_scheme() -> None:
    assert build_backend_url("127.0.0.1", 8765, "https://127.0.0.1:8741") == "https://127.0.0.1:8765"
