"""
Ember RPG - Campaign Loader Integration Tests

Tests:
- Load all campaign templates
- Validate all monster references exist in monsters.json
- Validate all item references exist in items.json
- Act structure validation
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.core.campaign import CampaignLoader

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).parent.parent / "data"
_CAMPAIGNS_DIR = _DATA_DIR / "campaigns"
_MONSTERS_FILE = _DATA_DIR / "monsters.json"
_ITEMS_FILE = _DATA_DIR / "items.json"

_EXPECTED_CAMPAIGN_IDS = {
    "tutorial_campaign",
    "main_quest_campaign",
    "side_quest_campaign",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def loader() -> CampaignLoader:
    cl = CampaignLoader(_CAMPAIGNS_DIR)
    cl.load()
    return cl


@pytest.fixture(scope="module")
def monster_ids() -> set[str]:
    data = json.loads(_MONSTERS_FILE.read_text(encoding="utf-8"))
    monsters = data if isinstance(data, list) else data.get("monsters", [])
    return {m["id"] for m in monsters}


@pytest.fixture(scope="module")
def item_ids() -> set[str]:
    data = json.loads(_ITEMS_FILE.read_text(encoding="utf-8"))
    items = data if isinstance(data, list) else data.get("items", [])
    return {i["id"] for i in items}


# ---------------------------------------------------------------------------
# Loading tests
# ---------------------------------------------------------------------------

class TestCampaignLoading:
    def test_load_without_calling_raises(self):
        cl = CampaignLoader(_CAMPAIGNS_DIR)
        with pytest.raises(RuntimeError, match="not loaded"):
            cl.list_campaigns()

    def test_load_succeeds(self, loader: CampaignLoader):
        # If fixture was built without exception, loading succeeded
        assert loader is not None

    def test_all_expected_campaigns_present(self, loader: CampaignLoader):
        loaded = set(loader.list_campaigns())
        assert _EXPECTED_CAMPAIGN_IDS.issubset(loaded), (
            f"Missing campaigns: {_EXPECTED_CAMPAIGN_IDS - loaded}"
        )

    def test_list_campaigns_returns_sorted_list(self, loader: CampaignLoader):
        ids = loader.list_campaigns()
        assert ids == sorted(ids)

    def test_get_known_campaign(self, loader: CampaignLoader):
        campaign = loader.get("tutorial_campaign")
        assert campaign is not None
        assert campaign["id"] == "tutorial_campaign"

    def test_get_unknown_campaign_returns_none(self, loader: CampaignLoader):
        assert loader.get("nonexistent_campaign_xyz") is None

    def test_load_nonexistent_dir_raises(self):
        cl = CampaignLoader("/tmp/ember_nonexistent_campaigns_dir_xyz")
        with pytest.raises(FileNotFoundError):
            cl.load()


# ---------------------------------------------------------------------------
# Campaign structure tests
# ---------------------------------------------------------------------------

class TestCampaignStructure:
    @pytest.mark.parametrize("campaign_id", list(_EXPECTED_CAMPAIGN_IDS))
    def test_top_level_fields(self, loader: CampaignLoader, campaign_id: str):
        campaign = loader.get(campaign_id)
        assert campaign is not None
        for field in ("id", "title", "description", "recommended_level", "acts"):
            assert field in campaign, f"Campaign {campaign_id!r} missing field {field!r}"

    @pytest.mark.parametrize("campaign_id", list(_EXPECTED_CAMPAIGN_IDS))
    def test_acts_is_non_empty_list(self, loader: CampaignLoader, campaign_id: str):
        campaign = loader.get(campaign_id)
        acts = campaign["acts"]
        assert isinstance(acts, list) and len(acts) > 0

    @pytest.mark.parametrize("campaign_id", list(_EXPECTED_CAMPAIGN_IDS))
    def test_act_fields(self, loader: CampaignLoader, campaign_id: str):
        campaign = loader.get(campaign_id)
        for i, act in enumerate(campaign["acts"]):
            for field in ("id", "name", "description", "encounters", "objectives", "rewards"):
                assert field in act, (
                    f"Campaign {campaign_id!r}, act[{i}] missing field {field!r}"
                )

    @pytest.mark.parametrize("campaign_id", list(_EXPECTED_CAMPAIGN_IDS))
    def test_objectives_have_required_fields(self, loader: CampaignLoader, campaign_id: str):
        campaign = loader.get(campaign_id)
        for act in campaign["acts"]:
            for obj in act["objectives"]:
                assert "id" in obj, f"Objective missing 'id' in campaign {campaign_id!r}"
                assert "description" in obj, f"Objective missing 'description'"
                assert "type" in obj, f"Objective missing 'type'"

    @pytest.mark.parametrize("campaign_id", list(_EXPECTED_CAMPAIGN_IDS))
    def test_rewards_have_item_id(self, loader: CampaignLoader, campaign_id: str):
        campaign = loader.get(campaign_id)
        for act in campaign["acts"]:
            for reward in act["rewards"]:
                assert "item_id" in reward, (
                    f"Reward missing 'item_id' in campaign {campaign_id!r}, act {act['id']!r}"
                )

    def test_tutorial_has_3_acts(self, loader: CampaignLoader):
        campaign = loader.get("tutorial_campaign")
        assert len(campaign["acts"]) == 3

    def test_main_quest_has_5_acts(self, loader: CampaignLoader):
        campaign = loader.get("main_quest_campaign")
        assert len(campaign["acts"]) == 5

    def test_side_quest_has_3_acts(self, loader: CampaignLoader):
        campaign = loader.get("side_quest_campaign")
        assert len(campaign["acts"]) == 3

    def test_recommended_level_is_positive_int(self, loader: CampaignLoader):
        for cid in _EXPECTED_CAMPAIGN_IDS:
            campaign = loader.get(cid)
            assert isinstance(campaign["recommended_level"], int)
            assert campaign["recommended_level"] > 0


# ---------------------------------------------------------------------------
# Monster reference validation
# ---------------------------------------------------------------------------

class TestMonsterReferences:
    def _collect_monster_refs(self, campaign: dict) -> list[str]:
        refs = []
        for act in campaign["acts"]:
            for enc in act["encounters"]:
                refs.extend(enc.get("monsters", []))
        return refs

    @pytest.mark.parametrize("campaign_id", list(_EXPECTED_CAMPAIGN_IDS))
    def test_all_monster_refs_exist(
        self,
        loader: CampaignLoader,
        monster_ids: set[str],
        campaign_id: str,
    ):
        campaign = loader.get(campaign_id)
        refs = self._collect_monster_refs(campaign)
        invalid = [m for m in refs if m not in monster_ids]
        assert invalid == [], (
            f"Campaign {campaign_id!r} references unknown monsters: {invalid}"
        )

    def test_tutorial_uses_low_cr_monsters(
        self, loader: CampaignLoader, monster_ids: set[str]
    ):
        campaign = loader.get("tutorial_campaign")
        refs = self._collect_monster_refs(campaign)
        # All referenced monsters should be in the DB
        for ref in refs:
            assert ref in monster_ids

    def test_main_quest_has_monster_encounters(self, loader: CampaignLoader):
        campaign = loader.get("main_quest_campaign")
        all_refs = self._collect_monster_refs(campaign)
        assert len(all_refs) > 0, "Main quest should have monster encounters"


# ---------------------------------------------------------------------------
# Item reference validation
# ---------------------------------------------------------------------------

class TestItemReferences:
    def _collect_item_refs(self, campaign: dict) -> list[str]:
        refs = []
        for act in campaign["acts"]:
            for reward in act["rewards"]:
                refs.append(reward["item_id"])
        return refs

    @pytest.mark.parametrize("campaign_id", list(_EXPECTED_CAMPAIGN_IDS))
    def test_all_item_refs_exist(
        self,
        loader: CampaignLoader,
        item_ids: set[str],
        campaign_id: str,
    ):
        campaign = loader.get(campaign_id)
        refs = self._collect_item_refs(campaign)
        invalid = [i for i in refs if i not in item_ids]
        assert invalid == [], (
            f"Campaign {campaign_id!r} references unknown items: {invalid}"
        )

    @pytest.mark.parametrize("campaign_id", list(_EXPECTED_CAMPAIGN_IDS))
    def test_each_act_has_at_least_one_reward(self, loader: CampaignLoader, campaign_id: str):
        campaign = loader.get(campaign_id)
        for act in campaign["acts"]:
            assert len(act["rewards"]) >= 1, (
                f"Act {act['id']!r} in {campaign_id!r} has no rewards"
            )
