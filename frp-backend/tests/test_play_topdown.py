import importlib
import sys
import types

from engine.api.game_engine import GameEngine


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


class _DummyTable:
    def __init__(self, *args, **kwargs):
        pass

    def add_column(self, *args, **kwargs):
        pass

    def add_row(self, *args, **kwargs):
        pass


class _DummyText:
    def __init__(self, *args, **kwargs):
        self.parts = []

    def append(self, text, style=None):
        self.parts.append((text, style))

    def append_text(self, other):
        self.parts.extend(getattr(other, "parts", []))


class _DummyLayout:
    def __init__(self, *args, **kwargs):
        pass

    def split_column(self, *args, **kwargs):
        pass

    def split_row(self, *args, **kwargs):
        pass

    def update(self, *args, **kwargs):
        pass

    def __getitem__(self, key):
        return self


class _DummyPrompt:
    @staticmethod
    def ask(*args, **kwargs):
        return kwargs.get("default", "")


class _DummyRule:
    def __init__(self, *args, **kwargs):
        pass


def _install_topdown_stubs(monkeypatch):
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
    table_module = types.ModuleType("rich.table")
    text_module = types.ModuleType("rich.text")
    layout_module = types.ModuleType("rich.layout")
    prompt_module = types.ModuleType("rich.prompt")
    rule_module = types.ModuleType("rich.rule")
    markup_module = types.ModuleType("rich.markup")

    console_module.Console = _DummyConsole
    panel_module.Panel = _DummyPanel
    table_module.Table = _DummyTable
    text_module.Text = _DummyText
    layout_module.Layout = _DummyLayout
    prompt_module.Prompt = _DummyPrompt
    rule_module.Rule = _DummyRule
    markup_module.escape = lambda text: text

    rich_module.console = console_module
    rich_module.panel = panel_module
    rich_module.table = table_module
    rich_module.text = text_module
    rich_module.layout = layout_module
    rich_module.prompt = prompt_module
    rich_module.rule = rule_module
    rich_module.markup = markup_module

    monkeypatch.setitem(sys.modules, "readchar", readchar_module)
    monkeypatch.setitem(sys.modules, "rich", rich_module)
    monkeypatch.setitem(sys.modules, "rich.console", console_module)
    monkeypatch.setitem(sys.modules, "rich.panel", panel_module)
    monkeypatch.setitem(sys.modules, "rich.table", table_module)
    monkeypatch.setitem(sys.modules, "rich.text", text_module)
    monkeypatch.setitem(sys.modules, "rich.layout", layout_module)
    monkeypatch.setitem(sys.modules, "rich.prompt", prompt_module)
    monkeypatch.setitem(sys.modules, "rich.rule", rule_module)
    monkeypatch.setitem(sys.modules, "rich.markup", markup_module)


def test_render_map_smoke(monkeypatch):
    _install_topdown_stubs(monkeypatch)
    sys.modules.pop("tools.play_topdown", None)

    play_topdown = importlib.import_module("tools.play_topdown")

    engine = GameEngine(llm=None)
    session = engine.new_session("Renderer", "warrior", location="Harbor Town")
    map_state = play_topdown.MapState(session)

    panel = play_topdown.render_map(map_state)

    assert panel is not None


def test_render_header_uses_combat_ap(monkeypatch):
    _install_topdown_stubs(monkeypatch)
    sys.modules.pop("tools.play_topdown", None)

    play_topdown = importlib.import_module("tools.play_topdown")

    engine = GameEngine(llm=None)
    session = engine.new_session("Renderer", "warrior", location="Harbor Town")
    engine.process_action(session, "attack")

    panel = play_topdown.render_header(session)
    rendered = panel.args[0]

    assert "AP: 3/3" in rendered


def test_render_character_sheet_includes_creation_summary(monkeypatch):
    _install_topdown_stubs(monkeypatch)
    sys.modules.pop("tools.play_topdown", None)

    play_topdown = importlib.import_module("tools.play_topdown")

    panel = play_topdown.render_character_sheet(
        {
            "character_sheet": {
                "name": "Renderer",
                "class": "warrior",
                "alignment": "LG",
                "stats": [
                    {"ability": "MIG", "value": 16, "modifier": 3},
                ],
                "skills": ["athletics"],
                "hp": {"current": 12, "max": 12},
                "sp": {"current": 4, "max": 4},
                "ap": {"current": 3, "max": 3},
                "creation_summary": {
                    "recommended_class": "warrior",
                    "recommended_alignment": "LG",
                    "current_roll": [16, 14, 12, 10, 8, 8],
                    "saved_roll": [14, 12, 12, 10, 9, 8],
                },
            }
        }
    )

    rendered = panel.args[0]
    assert any("Creation" in part for part, _style in rendered.parts)
    assert any("Recommended" in part for part, _style in rendered.parts)


def test_character_creation_smoke(monkeypatch):
    _install_topdown_stubs(monkeypatch)
    sys.modules.pop("tools.play_topdown", None)

    play_topdown = importlib.import_module("tools.play_topdown")
    monkeypatch.setattr(play_topdown.time, "sleep", lambda *_args, **_kwargs: None)

    creation = play_topdown.character_creation()

    assert creation["name"] == "Stranger"
    assert creation["player_class"] in {"warrior", "rogue", "mage", "priest"}
    assert creation["map_type"] in {"town", "dungeon", "wilderness"}
    assert creation["stats"]
    assert creation["character_sheet"]["name"] == "Stranger"
    assert creation["creation_state"]["questions"]


def test_start_or_load_campaign_can_load_existing_save(monkeypatch):
    _install_topdown_stubs(monkeypatch)
    sys.modules.pop("tools.play_topdown", None)

    play_topdown = importlib.import_module("tools.play_topdown")

    answers = iter(["load", "Chaos", "1"])
    monkeypatch.setattr(play_topdown.Prompt, "ask", lambda *args, **kwargs: next(answers))

    class DummyClient:
        def list_saves_for_player(self, player_id):
            assert player_id == "Chaos"
            return [
                {"save_id": "slot_a", "slot_name": "slot_a", "location": "Harbor Town", "timestamp": "2026-03-28T10:00:00"},
                {"save_id": "slot_b", "slot_name": "slot_b", "location": "Forest Edge", "timestamp": "2026-03-28T11:00:00"},
            ]

        def load_campaign(self, save_id):
            assert save_id == "slot_a"
            return {"campaign_id": "camp_loaded", "narrative": "Loaded."}

    snapshot = play_topdown.start_or_load_campaign(DummyClient())

    assert snapshot["campaign_id"] == "camp_loaded"


def test_start_or_load_campaign_invalid_save_input_falls_back_to_new(monkeypatch):
    _install_topdown_stubs(monkeypatch)
    sys.modules.pop("tools.play_topdown", None)

    play_topdown = importlib.import_module("tools.play_topdown")

    answers = iter(["load", "Chaos", "bogus", "new"])
    monkeypatch.setattr(play_topdown.Prompt, "ask", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(play_topdown, "character_creation", lambda client=None: {"campaign_id": "camp_new"})

    class DummyClient:
        def list_saves_for_player(self, player_id):
            assert player_id == "Chaos"
            return [{"save_id": "slot_a", "slot_name": "slot_a", "location": "Harbor Town", "timestamp": "2026-03-28T10:00:00"}]

        def load_campaign(self, save_id):
            raise AssertionError("load_campaign should not be called for invalid selection fallback")

    snapshot = play_topdown.start_or_load_campaign(DummyClient())

    assert snapshot["campaign_id"] == "camp_new"
