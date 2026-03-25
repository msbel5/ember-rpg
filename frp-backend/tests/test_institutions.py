"""
Tests for engine.world.institutions -- Law & Institution Layer (AC-31..AC-33)
"""
import pytest

from engine.world.institutions import (
    TOWN_INSTITUTIONS,
    InstitutionManager,
    InstitutionalResponse,
    PowerVacuumEffect,
)


# ---------------------------------------------------------------------------
# AC-31: Institution data completeness
# ---------------------------------------------------------------------------

class TestInstitutionData:
    """Verify harbor_town institution definitions."""

    def test_harbor_town_has_7_roles(self):
        assert len(TOWN_INSTITUTIONS["harbor_town"]) == 7

    def test_all_roles_have_holders(self):
        for role_id, role in TOWN_INSTITUTIONS["harbor_town"].items():
            assert role.holder_name is not None, f"{role_id} has no holder"
            assert len(role.holder_name) > 0

    def test_all_roles_have_responsibilities(self):
        for role_id, role in TOWN_INSTITUTIONS["harbor_town"].items():
            assert len(role.responsibilities) >= 2, f"{role_id} needs more responsibilities"

    def test_authority_levels_are_valid(self):
        for role_id, role in TOWN_INSTITUTIONS["harbor_town"].items():
            assert 1 <= role.authority_level <= 10

    def test_mayor_has_highest_authority(self):
        mayor = TOWN_INSTITUTIONS["harbor_town"]["mayor"]
        for role_id, role in TOWN_INSTITUTIONS["harbor_town"].items():
            assert role.authority_level <= mayor.authority_level


# ---------------------------------------------------------------------------
# AC-32: handle_event responses
# ---------------------------------------------------------------------------

class TestHandleEvent:
    """Test institutional responses to events."""

    @pytest.fixture()
    def manager(self):
        return InstitutionManager()

    def test_murder_low_triggers_investigation(self, manager):
        responses = manager.handle_event("murder", "low", "harbor_town")
        types = [r.response_type for r in responses]
        assert "investigation" in types

    def test_murder_critical_triggers_martial_law(self, manager):
        responses = manager.handle_event("murder", "critical", "harbor_town")
        types = [r.response_type for r in responses]
        assert "martial_law" in types

    def test_theft_medium_triggers_bounty(self, manager):
        responses = manager.handle_event("theft", "medium", "harbor_town")
        types = [r.response_type for r in responses]
        assert "bounty" in types

    def test_unknown_town_returns_empty(self, manager):
        responses = manager.handle_event("murder", "high", "nonexistent_town")
        assert responses == []

    def test_unknown_event_returns_empty(self, manager):
        responses = manager.handle_event("alien_invasion_from_space", "high", "harbor_town")
        assert responses == []

    def test_responses_are_institutional_response_objects(self, manager):
        responses = manager.handle_event("riot", "high", "harbor_town")
        for r in responses:
            assert isinstance(r, InstitutionalResponse)

    def test_higher_severity_includes_lower_responses(self, manager):
        low = manager.handle_event("murder", "low", "harbor_town")
        high = manager.handle_event("murder", "high", "harbor_town")
        assert len(high) >= len(low)

    def test_desecration_triggers_sanctuary(self, manager):
        responses = manager.handle_event("desecration", "low", "harbor_town")
        types = [r.response_type for r in responses]
        assert "sanctuary" in types


# ---------------------------------------------------------------------------
# AC-33: Authority chain and power vacuum
# ---------------------------------------------------------------------------

class TestAuthorityChain:
    """Test get_authority and remove_official."""

    @pytest.fixture()
    def manager(self):
        return InstitutionManager()

    def test_guard_captain_chain_goes_to_mayor(self, manager):
        chain = manager.get_authority("harbor_town", "guard_captain")
        assert chain == ["guard_captain", "mayor"]

    def test_mayor_chain_is_just_mayor(self, manager):
        chain = manager.get_authority("harbor_town", "mayor")
        assert chain == ["mayor"]

    def test_tax_collector_chain(self, manager):
        chain = manager.get_authority("harbor_town", "tax_collector")
        assert "tax_collector" in chain
        assert "harbormaster" in chain

    def test_unknown_town_returns_empty_chain(self, manager):
        chain = manager.get_authority("ghost_town", "mayor")
        assert chain == []

    def test_remove_official_returns_vacuum_effect(self, manager):
        effect = manager.remove_official("harbor_town", "guard_captain")
        assert isinstance(effect, PowerVacuumEffect)
        assert effect.removed_role == "guard_captain"
        assert effect.chaos_level > 0
        assert len(effect.effects) > 0

    def test_removed_official_is_no_longer_active(self, manager):
        assert manager.is_official_active("harbor_town", "guard_captain") is True
        manager.remove_official("harbor_town", "guard_captain")
        assert manager.is_official_active("harbor_town", "guard_captain") is False

    def test_removing_mayor_causes_high_chaos(self, manager):
        effect = manager.remove_official("harbor_town", "mayor")
        assert effect.chaos_level >= 70

    def test_multiple_removals_increase_chaos(self, manager):
        e1 = manager.remove_official("harbor_town", "guard_captain")
        e2 = manager.remove_official("harbor_town", "magistrate")
        # Second removal should have escalated chaos
        assert e2.chaos_level >= 50

    def test_removed_official_cannot_issue_responses(self, manager):
        manager.remove_official("harbor_town", "guard_captain")
        responses = manager.handle_event("murder", "low", "harbor_town")
        for r in responses:
            assert r.issuer_role != "guard_captain"

    def test_get_active_officials_excludes_removed(self, manager):
        manager.remove_official("harbor_town", "harbormaster")
        active = manager.get_active_officials("harbor_town")
        assert "harbormaster" not in active
        assert "mayor" in active
