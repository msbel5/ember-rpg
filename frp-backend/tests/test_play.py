import importlib
import sys
import types


class _DummyConsole:
    def __init__(self, *args, **kwargs):
        pass

    def print(self, *args, **kwargs):
        pass

    def clear(self):
        pass


class _DummyPanel:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class _DummyPrompt:
    @staticmethod
    def ask(*args, **kwargs):
        return kwargs.get("default", "")


class _DummyRule:
    def __init__(self, *args, **kwargs):
        pass


def _install_play_stubs(monkeypatch):
    readchar_module = types.ModuleType("readchar")
    readchar_module.key = types.SimpleNamespace(
        UP="UP",
        DOWN="DOWN",
        LEFT="LEFT",
        RIGHT="RIGHT",
        ENTER="ENTER",
        BACKSPACE="BACKSPACE",
        CTRL_C="CTRL_C",
    )
    readchar_module.readkey = lambda: "q"

    rich_module = types.ModuleType("rich")
    console_module = types.ModuleType("rich.console")
    panel_module = types.ModuleType("rich.panel")
    prompt_module = types.ModuleType("rich.prompt")
    rule_module = types.ModuleType("rich.rule")
    layout_module = types.ModuleType("rich.layout")
    table_module = types.ModuleType("rich.table")
    text_module = types.ModuleType("rich.text")
    markup_module = types.ModuleType("rich.markup")

    console_module.Console = _DummyConsole
    panel_module.Panel = _DummyPanel
    prompt_module.Prompt = _DummyPrompt
    rule_module.Rule = _DummyRule
    layout_module.Layout = type("Layout", (), {})
    table_module.Table = type("Table", (), {"__init__": lambda self, *a, **k: None, "add_column": lambda self, *a, **k: None, "add_row": lambda self, *a, **k: None})
    text_module.Text = type("Text", (), {"__init__": lambda self, *a, **k: None, "append": lambda self, *a, **k: None, "append_text": lambda self, *a, **k: None})
    markup_module.escape = lambda text: text

    rich_module.console = console_module
    rich_module.panel = panel_module
    rich_module.prompt = prompt_module
    rich_module.rule = rule_module
    rich_module.layout = layout_module
    rich_module.table = table_module
    rich_module.text = text_module
    rich_module.markup = markup_module

    monkeypatch.setitem(sys.modules, "readchar", readchar_module)
    monkeypatch.setitem(sys.modules, "rich", rich_module)
    monkeypatch.setitem(sys.modules, "rich.console", console_module)
    monkeypatch.setitem(sys.modules, "rich.panel", panel_module)
    monkeypatch.setitem(sys.modules, "rich.prompt", prompt_module)
    monkeypatch.setitem(sys.modules, "rich.rule", rule_module)
    monkeypatch.setitem(sys.modules, "rich.layout", layout_module)
    monkeypatch.setitem(sys.modules, "rich.table", table_module)
    monkeypatch.setitem(sys.modules, "rich.text", text_module)
    monkeypatch.setitem(sys.modules, "rich.markup", markup_module)


def test_play_meta_save_uses_snapshot_player(monkeypatch):
    _install_play_stubs(monkeypatch)
    sys.modules.pop("tools.play", None)
    sys.modules.pop("tools.play_topdown", None)

    play = importlib.import_module("tools.play")

    class DummyClient:
        def __init__(self):
            self.saved = None

        def save_campaign(self, campaign_id, slot_name, player_id):
            self.saved = (campaign_id, slot_name, player_id)
            return {"slot_name": slot_name}

    client = DummyClient()
    snapshot = {
        "campaign_id": "camp_1",
        "campaign": {"player": {"name": "Chaos"}},
    }
    history = []

    handled, new_snapshot = play._handle_meta_command(client, snapshot, history, "save demo_slot")

    assert handled is True
    assert new_snapshot is snapshot
    assert client.saved == ("camp_1", "demo_slot", "Chaos")
    assert history[-1] == "Saved to demo_slot."


def test_play_meta_saves_uses_player_discovery(monkeypatch):
    _install_play_stubs(monkeypatch)
    sys.modules.pop("tools.play", None)
    sys.modules.pop("tools.play_topdown", None)

    play = importlib.import_module("tools.play")

    class DummyClient:
        def __init__(self):
            self.requested_player = None

        def list_saves_for_player(self, player_id):
            self.requested_player = player_id
            return [{"slot_name": "demo", "save_id": "demo", "location": "Harbor Town", "timestamp": "2026-03-28T10:00:00"}]

    client = DummyClient()
    snapshot = {
        "campaign_id": "camp_1",
        "campaign": {"player": {"name": "Chaos"}},
    }
    history = []

    handled, new_snapshot = play._handle_meta_command(client, snapshot, history, "saves")

    assert handled is True
    assert new_snapshot is snapshot
    assert client.requested_player == "Chaos"
    assert history[-1].startswith("demo | Harbor Town |")


def test_play_meta_saves_filters_incompatible_legacy_slots(monkeypatch):
    _install_play_stubs(monkeypatch)
    sys.modules.pop("tools.play", None)
    sys.modules.pop("tools.play_topdown", None)

    play = importlib.import_module("tools.play")

    class DummyClient:
        def list_saves_for_player(self, player_id):
            assert player_id == "Chaos"
            return [
                {"slot_name": "legacy_slot", "save_id": "legacy_slot", "location": "Harbor Town", "timestamp": "2026-03-28T10:00:00", "campaign_compatible": False},
                {"slot_name": "demo", "save_id": "demo", "location": "Dragon Eyrie", "timestamp": "2026-03-28T10:05:00", "campaign_compatible": True},
            ]

    snapshot = {
        "campaign_id": "camp_1",
        "campaign": {"player": {"name": "Chaos"}},
    }
    history = []

    handled, new_snapshot = play._handle_meta_command(DummyClient(), snapshot, history, "saves")

    assert handled is True
    assert new_snapshot is snapshot
    assert len(history) == 1
    assert history[-1].startswith("demo | Dragon Eyrie |")


def test_play_meta_saves_reports_no_campaign_slots_when_only_legacy(monkeypatch):
    _install_play_stubs(monkeypatch)
    sys.modules.pop("tools.play", None)
    sys.modules.pop("tools.play_topdown", None)

    play = importlib.import_module("tools.play")

    class DummyClient:
        def list_saves_for_player(self, player_id):
            assert player_id == "Chaos"
            return [{"slot_name": "legacy_slot", "save_id": "legacy_slot", "campaign_compatible": False}]

    snapshot = {
        "campaign_id": "camp_1",
        "campaign": {"player": {"name": "Chaos"}},
    }
    history = []

    handled, new_snapshot = play._handle_meta_command(DummyClient(), snapshot, history, "saves")

    assert handled is True
    assert new_snapshot is snapshot
    assert history[-1] == "No campaign-compatible save slots found."


def test_play_meta_load_without_slot_uses_browser(monkeypatch):
    _install_play_stubs(monkeypatch)
    sys.modules.pop("tools.play", None)
    sys.modules.pop("tools.play_topdown", None)

    play = importlib.import_module("tools.play")
    monkeypatch.setattr(play, "browse_campaign_saves", lambda client, default_player_id="": {"campaign_id": "camp_loaded", "narrative": "Loaded."})

    class DummyClient:
        pass

    snapshot = {
        "campaign_id": "camp_1",
        "campaign": {"player": {"name": "Chaos"}},
    }
    history = ["old line"]

    handled, new_snapshot = play._handle_meta_command(DummyClient(), snapshot, history, "load")

    assert handled is True
    assert new_snapshot["campaign_id"] == "camp_loaded"
    assert history == ["Loaded."]
