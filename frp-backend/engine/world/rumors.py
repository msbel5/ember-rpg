"""
Rumor propagation network for Ember RPG.
FR-57..FR-59: Rumors with confidence, spread, decay, faction filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class Rumor:
    """A single rumor circulating in the world."""
    rumor_id: str
    fact: str                       # the actual claim
    source_npc: str                 # NPC who started it
    confidence: float               # 0.0‑1.0, drops over time
    timestamp: float                # game-hour when created
    spread_radius: int = 1          # max hops from origin location
    faction_filter: Optional[str] = None   # only spreads within this faction
    decay_rate: float = 0.02        # confidence lost per game-hour
    locations: Set[str] = field(default_factory=set)   # location_ids that know it
    heard_by: Set[str] = field(default_factory=set)     # npc_ids that heard it


@dataclass
class NPCInfo:
    """Lightweight NPC descriptor for rumor propagation."""
    npc_id: str
    location: str
    faction: Optional[str] = None


class RumorNetwork:
    """Manages creation, propagation, and decay of rumors."""

    def __init__(self) -> None:
        self.rumors: Dict[str, Rumor] = {}
        self._next_id: int = 1

    # ── creation ─────────────────────────────────────────────────────
    def add_rumor(
        self,
        fact: str,
        source_npc: str,
        location: str,
        confidence: float = 0.8,
        timestamp: float = 0.0,
        spread_radius: int = 1,
        faction_filter: Optional[str] = None,
        decay_rate: float = 0.02,
    ) -> Rumor:
        rid = f"rumor_{self._next_id}"
        self._next_id += 1
        r = Rumor(
            rumor_id=rid,
            fact=fact,
            source_npc=source_npc,
            confidence=min(1.0, max(0.0, confidence)),
            timestamp=timestamp,
            spread_radius=spread_radius,
            faction_filter=faction_filter,
            decay_rate=decay_rate,
            locations={location},
            heard_by={source_npc},
        )
        self.rumors[rid] = r
        return r

    # ── propagation ──────────────────────────────────────────────────
    def propagate(self, npcs_at_location: List[NPCInfo]) -> List[Dict]:
        """Spread rumors to NPCs present at the same location.

        Returns a list of ``{rumor_id, npc_id}`` dicts for each new hearing.
        """
        events: List[Dict] = []
        for npc in npcs_at_location:
            for rumor in self.rumors.values():
                if rumor.confidence <= 0:
                    continue
                # Location check
                if npc.location not in rumor.locations:
                    continue
                # Faction filter
                if rumor.faction_filter and npc.faction != rumor.faction_filter:
                    continue
                # Already heard?
                if npc.npc_id in rumor.heard_by:
                    continue
                rumor.heard_by.add(npc.npc_id)
                events.append({"rumor_id": rumor.rumor_id, "npc_id": npc.npc_id})
        return events

    def spread_to_location(self, rumor_id: str, location: str) -> bool:
        """Manually spread a rumor to a new location (within spread_radius logic).

        Returns True if the location was newly added.
        """
        rumor = self.rumors.get(rumor_id)
        if rumor is None:
            return False
        if len(rumor.locations) >= rumor.spread_radius + 1:
            return False
        if location in rumor.locations:
            return False
        rumor.locations.add(location)
        return True

    # ── decay ────────────────────────────────────────────────────────
    def decay(self, hours: float) -> List[str]:
        """Reduce confidence of all rumors by their decay_rate * hours.

        Returns list of rumor_ids that dropped to zero (expired).
        """
        expired: List[str] = []
        for rid, rumor in list(self.rumors.items()):
            rumor.confidence = max(0.0, rumor.confidence - rumor.decay_rate * hours)
            if rumor.confidence <= 0:
                expired.append(rid)
        return expired

    def prune_expired(self) -> int:
        """Remove all rumors with confidence ≤ 0. Returns count removed."""
        to_del = [rid for rid, r in self.rumors.items() if r.confidence <= 0]
        for rid in to_del:
            del self.rumors[rid]
        return len(to_del)

    # ── queries ──────────────────────────────────────────────────────
    def get_rumors_for_npc(self, npc: NPCInfo) -> List[Rumor]:
        """Return all active rumors an NPC has heard or can hear now."""
        result: List[Rumor] = []
        for rumor in self.rumors.values():
            if rumor.confidence <= 0:
                continue
            if rumor.faction_filter and npc.faction != rumor.faction_filter:
                continue
            if npc.npc_id in rumor.heard_by:
                result.append(rumor)
                continue
            if npc.location in rumor.locations:
                result.append(rumor)
        return result

    def get_all_active(self) -> List[Rumor]:
        return [r for r in self.rumors.values() if r.confidence > 0]

    def to_dict(self) -> dict:
        """Serialize rumor network for save/load."""
        return {
            "next_id": self._next_id,
            "rumors": {
                rid: {
                    "rumor_id": r.rumor_id,
                    "fact": r.fact,
                    "source_npc": r.source_npc,
                    "confidence": r.confidence,
                    "timestamp": r.timestamp,
                    "spread_radius": r.spread_radius,
                    "faction_filter": r.faction_filter,
                    "decay_rate": r.decay_rate,
                    "locations": list(r.locations),
                    "heard_by": list(r.heard_by),
                }
                for rid, r in self.rumors.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RumorNetwork":
        """Deserialize rumor network from a dict."""
        rn = cls()
        rn._next_id = data.get("next_id", 1)
        for rid, rd in data.get("rumors", {}).items():
            rn.rumors[rid] = Rumor(
                rumor_id=rd["rumor_id"],
                fact=rd["fact"],
                source_npc=rd["source_npc"],
                confidence=rd["confidence"],
                timestamp=rd["timestamp"],
                spread_radius=rd.get("spread_radius", 1),
                faction_filter=rd.get("faction_filter"),
                decay_rate=rd.get("decay_rate", 0.02),
                locations=set(rd.get("locations", [])),
                heard_by=set(rd.get("heard_by", [])),
            )
        return rn
