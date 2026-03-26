"""Timed condition helpers for GameSession."""
from __future__ import annotations

from typing import Any, Dict, List


class SessionTimedConditionMixin:
    """Timed-condition and game-time helpers."""

    def _get_strength_modifier(self) -> int:
        if self.player is None:
            return 0
        mig = (getattr(self.player, "stats", None) or {}).get("MIG", 10)
        return (mig - 10) // 2

    def current_game_hour(self) -> float:
        if not getattr(self, "game_time", None):
            return 0.0
        return ((self.game_time.day - 1) * 24) + self.game_time.hour + (self.game_time.minute / 60.0)

    def timed_condition_payload(self) -> List[Dict[str, Any]]:
        now = self.current_game_hour()
        payload: List[Dict[str, Any]] = []
        for name, data in sorted(self.timed_conditions.items()):
            expires_at = float(data.get("expires_at_hour", now))
            remaining_hours = max(0.0, expires_at - now)
            payload.append({
                "name": name,
                "expires_at_hour": expires_at,
                "remaining_hours": round(remaining_hours, 2),
                "remaining_minutes": max(0, int(round(remaining_hours * 60))),
                "movement_ap_penalty": int(data.get("movement_ap_penalty", 0)),
                "agi_check_penalty": int(data.get("agi_check_penalty", 0)),
            })
        return payload

    def active_timed_conditions(self) -> Dict[str, Dict[str, Any]]:
        now = self.current_game_hour()
        active: Dict[str, Dict[str, Any]] = {}
        for name, data in self.timed_conditions.items():
            expires_at = float(data.get("expires_at_hour", now))
            if expires_at > now:
                active[name] = dict(data)
        return active

    def clear_expired_timed_conditions(self) -> List[str]:
        expired = [
            name
            for name, data in self.timed_conditions.items()
            if float(data.get("expires_at_hour", self.current_game_hour())) <= self.current_game_hour()
        ]
        for name in expired:
            self.timed_conditions.pop(name, None)
        return expired

    def has_timed_condition(self, name: str) -> bool:
        self.clear_expired_timed_conditions()
        return name in self.timed_conditions

    def apply_timed_condition(
        self,
        name: str,
        duration_hours: float,
        *,
        movement_ap_penalty: int = 0,
        agi_check_penalty: int = 0,
    ) -> Dict[str, Any]:
        expires_at = self.current_game_hour() + max(0.0, float(duration_hours))
        current = dict(self.timed_conditions.get(name, {}))
        current["name"] = name
        current["expires_at_hour"] = max(float(current.get("expires_at_hour", 0.0)), expires_at)
        current["movement_ap_penalty"] = max(int(current.get("movement_ap_penalty", 0)), int(movement_ap_penalty))
        current["agi_check_penalty"] = max(int(current.get("agi_check_penalty", 0)), int(agi_check_penalty))
        self.timed_conditions[name] = current
        self.sync_player_state()
        return current
