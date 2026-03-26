"""
Ember RPG - Campaign Loader
Loads and validates campaign templates from data/campaigns/.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from engine.data_loader import load_json_path

# Default path relative to this file: engine/core/campaign.py → ../../data/campaigns
_DEFAULT_CAMPAIGNS_DIR = Path(__file__).parent.parent.parent / "data" / "campaigns"


class CampaignLoader:
    """Loads campaign JSON templates from disk.

    Usage::

        loader = CampaignLoader()
        loader.load()
        campaign = loader.get("tutorial_campaign")
        all_ids = loader.list_campaigns()
    """

    def __init__(self, campaigns_dir: Optional[Path | str] = None) -> None:
        self._dir: Path = Path(campaigns_dir) if campaigns_dir else _DEFAULT_CAMPAIGNS_DIR
        self._campaigns: Dict[str, dict] = {}
        self._loaded: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load all campaign JSON files from the campaigns directory.

        Raises FileNotFoundError if the directory does not exist.
        Raises ValueError if any JSON file cannot be parsed.
        """
        if not self._dir.exists():
            raise FileNotFoundError(
                f"Campaigns directory not found: {self._dir}"
            )

        self._campaigns.clear()
        for path in sorted(self._dir.glob("*.json")):
            try:
                data = load_json_path(path)
            except Exception as exc:
                raise ValueError(f"Failed to parse campaign file {path.name}: {exc}") from exc

            campaign_id = data.get("id") or path.stem
            self._campaigns[campaign_id] = data

        self._loaded = True

    def get(self, campaign_id: str) -> Optional[dict]:
        """Return campaign data dict by id, or None if not found.

        Raises RuntimeError if load() has not been called.
        """
        self._ensure_loaded()
        return self._campaigns.get(campaign_id)

    def list_campaigns(self) -> List[str]:
        """Return a sorted list of all loaded campaign ids.

        Raises RuntimeError if load() has not been called.
        """
        self._ensure_loaded()
        return sorted(self._campaigns.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            raise RuntimeError(
                "Campaigns not loaded. Call CampaignLoader.load() first."
            )

    @property
    def campaigns(self) -> Dict[str, dict]:
        """Direct access to the loaded campaigns dict (read-only intent)."""
        self._ensure_loaded()
        return self._campaigns
