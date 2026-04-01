"""
Ember RPG -- Law & Institution Layer (Sprint 3, Module 11)
FR-46..FR-49: Civic institutions, authority hierarchy, event responses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .institutions_catalog import load_institutions_registry


# ---------------------------------------------------------------------------
# Institutional response types
# ---------------------------------------------------------------------------

@dataclass
class InstitutionalResponse:
    """A single response issued by an institution."""
    response_type: str  # bounty, martial_law, price_floor, exile, arrest, sanctuary, investigation, curfew
    issuer_role: str
    description: str
    severity: str  # low, medium, high, critical
    duration_hours: Optional[int] = None
    target: Optional[str] = None
    parameters: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "response_type": self.response_type,
            "issuer_role": self.issuer_role,
            "description": self.description,
            "severity": self.severity,
            "duration_hours": self.duration_hours,
            "target": self.target,
            "parameters": self.parameters,
        }


@dataclass
class PowerVacuumEffect:
    """Effect of removing an official from their role."""
    removed_role: str
    town: str
    effects: list[str]
    successor: Optional[str] = None
    chaos_level: int = 0  # 0-100

    def to_dict(self) -> dict:
        return {
            "removed_role": self.removed_role,
            "town": self.town,
            "effects": self.effects,
            "successor": self.successor,
            "chaos_level": self.chaos_level,
        }


# ---------------------------------------------------------------------------
# Town institution definitions
# ---------------------------------------------------------------------------

@dataclass
class CivicRole:
    """Definition of a civic role within a town."""
    role_id: str
    title: str
    faction_affiliation: str
    authority_level: int  # 1-10
    responsibilities: list[str]
    can_issue: list[str]  # which response types they can issue
    reports_to: Optional[str] = None  # role_id of superior
    holder_name: Optional[str] = None  # current office holder

_REGISTRY = load_institutions_registry()


def _load_town_institutions() -> dict[str, dict[str, CivicRole]]:
    towns: dict[str, dict[str, CivicRole]] = {}
    for town_id, roles in _REGISTRY.get("town_institutions", {}).items():
        towns[town_id] = {
            role_id: CivicRole(**payload)
            for role_id, payload in roles.items()
        }
    return towns


TOWN_INSTITUTIONS: dict[str, dict[str, CivicRole]] = _load_town_institutions()

# ---------------------------------------------------------------------------
# Event response rules
# ---------------------------------------------------------------------------

_EVENT_RESPONSE_RULES: dict[str, list[dict]] = {
    event_type: list(rules)
    for event_type, rules in _REGISTRY.get("event_response_rules", {}).items()
}

_SEVERITY_ORDER = list(_REGISTRY.get("severity_order", ["low", "medium", "high", "critical"]))


def _severity_index(sev: str) -> int:
    try:
        return _SEVERITY_ORDER.index(sev.lower())
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Power vacuum effects
# ---------------------------------------------------------------------------

_VACUUM_EFFECTS: dict[str, dict] = {
    role_id: dict(payload)
    for role_id, payload in _REGISTRY.get("vacuum_effects", {}).items()
}


# ---------------------------------------------------------------------------
# InstitutionManager
# ---------------------------------------------------------------------------

class InstitutionManager:
    """Manages institutional responses to world events."""

    def __init__(self) -> None:
        # Track removed officials: town -> role_id -> True
        self._removed_officials: dict[str, set[str]] = {}

    def handle_event(
        self,
        event_type: str,
        severity: str,
        town: str,
    ) -> list[InstitutionalResponse]:
        """Determine institutional responses to a world event.

        Args:
            event_type: Type of event (murder, theft, riot, trade_disruption, desecration, invasion).
            severity: Severity level (low, medium, high, critical).
            town: Town identifier (e.g. 'harbor_town').

        Returns:
            List of InstitutionalResponse objects.
        """
        if town not in TOWN_INSTITUTIONS:
            return []

        rules = _EVENT_RESPONSE_RULES.get(event_type, [])
        if not rules:
            return []

        sev_idx = _severity_index(severity)
        responses: list[InstitutionalResponse] = []
        removed = self._removed_officials.get(town, set())

        for rule in rules:
            rule_sev_idx = _severity_index(rule["severity_min"])
            if sev_idx < rule_sev_idx:
                continue

            role_id = rule["role"]
            # If the official has been removed, skip unless someone else can issue it
            if role_id in removed:
                # Try to find a superior or replacement who can issue the same response
                replacement = self._find_replacement(town, role_id, rule["response"], removed)
                if replacement is None:
                    continue
                role_id = replacement

            role_def = TOWN_INSTITUTIONS[town].get(role_id)
            if role_def is None:
                continue

            # Check if this role can actually issue this response type
            if rule["response"] not in role_def.can_issue:
                continue

            response = InstitutionalResponse(
                response_type=rule["response"],
                issuer_role=role_id,
                description=rule["desc"],
                severity=severity,
                duration_hours=rule.get("duration"),
                target=None,
                parameters=rule.get("params", {}),
            )
            responses.append(response)

        return responses

    def get_authority(self, town: str, role: str) -> list[str]:
        """Get the chain of authority for a role in a town.

        Returns a list of role_ids from the given role up to the top.
        """
        if town not in TOWN_INSTITUTIONS:
            return []

        chain: list[str] = []
        current = role
        visited: set[str] = set()
        while current and current not in visited:
            if current not in TOWN_INSTITUTIONS[town]:
                break
            visited.add(current)
            chain.append(current)
            current = TOWN_INSTITUTIONS[town][current].reports_to
        return chain

    def remove_official(self, town: str, role: str) -> PowerVacuumEffect:
        """Remove an official from their post and calculate the resulting power vacuum.

        Args:
            town: Town identifier.
            role: Role id of the official to remove.

        Returns:
            PowerVacuumEffect describing the consequences.
        """
        if town not in self._removed_officials:
            self._removed_officials[town] = set()
        self._removed_officials[town].add(role)

        vacuum_info = _VACUUM_EFFECTS.get(role, {
            "effects": [f"The position of {role} is now vacant."],
            "chaos_level": 25,
            "potential_successors": [],
        })

        # Check if any potential successor is also removed
        removed = self._removed_officials.get(town, set())
        available_successors = [
            s for s in vacuum_info.get("potential_successors", [])
            if s not in removed
        ]
        successor = available_successors[0] if available_successors else None

        # Chaos increases if multiple officials are removed
        base_chaos = vacuum_info["chaos_level"]
        num_removed = len(removed)
        chaos_multiplier = 1.0 + 0.2 * (num_removed - 1)
        final_chaos = min(100, int(base_chaos * chaos_multiplier))

        effects = list(vacuum_info["effects"])
        if num_removed > 1:
            effects.append(f"With {num_removed} positions vacant, chaos escalates.")
        if successor:
            successor_def = TOWN_INSTITUTIONS.get(town, {}).get(successor)
            successor_name = successor_def.holder_name if successor_def else successor
            effects.append(f"{successor_name} assumes emergency authority.")

        return PowerVacuumEffect(
            removed_role=role,
            town=town,
            effects=effects,
            successor=successor,
            chaos_level=final_chaos,
        )

    def is_official_active(self, town: str, role: str) -> bool:
        """Check if an official is still active (not removed)."""
        removed = self._removed_officials.get(town, set())
        return role not in removed

    def get_active_officials(self, town: str) -> dict[str, CivicRole]:
        """Get all active (non-removed) officials for a town."""
        if town not in TOWN_INSTITUTIONS:
            return {}
        removed = self._removed_officials.get(town, set())
        return {
            role_id: role_def
            for role_id, role_def in TOWN_INSTITUTIONS[town].items()
            if role_id not in removed
        }

    def _find_replacement(
        self,
        town: str,
        removed_role: str,
        response_type: str,
        removed: set[str],
    ) -> Optional[str]:
        """Find a replacement official who can issue a given response type."""
        institutions = TOWN_INSTITUTIONS.get(town, {})
        # Check the superior first
        original = institutions.get(removed_role)
        if original and original.reports_to and original.reports_to not in removed:
            superior = institutions.get(original.reports_to)
            if superior and response_type in superior.can_issue:
                return original.reports_to

        # Check all active officials by authority level (descending)
        candidates = [
            (role_id, role_def)
            for role_id, role_def in institutions.items()
            if role_id not in removed and response_type in role_def.can_issue
        ]
        candidates.sort(key=lambda x: x[1].authority_level, reverse=True)
        if candidates:
            return candidates[0][0]
        return None
