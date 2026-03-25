"""
Quest timeout and deadline tracking for Ember RPG.
FR-63..FR-66: Timed quests with deadlines, reminders, consequences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional


class QuestStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class QuestEntry:
    """A tracked quest with an optional deadline."""
    quest_id: str
    title: str
    deadline_hour: Optional[float] = None     # game-hour, None = no deadline
    timeout_consequence: str = "quest_failed"  # tag for what happens on expiry
    reminder_hours: List[float] = field(default_factory=lambda: [24.0, 8.0, 1.0])
    status: QuestStatus = QuestStatus.ACTIVE
    accepted_hour: float = 0.0                 # when player accepted
    completed_hour: Optional[float] = None
    _reminders_sent: List[float] = field(default_factory=list)


class QuestTracker:
    """Manages timed quests, reminders, and expiry consequences."""

    def __init__(self) -> None:
        self.quests: Dict[str, QuestEntry] = {}
        self._consequence_handlers: Dict[str, Callable[[QuestEntry], Dict]] = {}

    # ── quest lifecycle ──────────────────────────────────────────────
    def add_quest(
        self,
        quest_id: str,
        title: str,
        current_hour: float,
        deadline_hour: Optional[float] = None,
        timeout_consequence: str = "quest_failed",
        reminder_hours: Optional[List[float]] = None,
    ) -> QuestEntry:
        entry = QuestEntry(
            quest_id=quest_id,
            title=title,
            deadline_hour=deadline_hour,
            timeout_consequence=timeout_consequence,
            reminder_hours=sorted(reminder_hours or [24.0, 8.0, 1.0], reverse=True),
            accepted_hour=current_hour,
        )
        self.quests[quest_id] = entry
        return entry

    def complete_quest(self, quest_id: str, current_hour: float) -> QuestEntry:
        """Mark quest as completed. Raises ``KeyError`` if not found."""
        q = self.quests[quest_id]
        if q.status != QuestStatus.ACTIVE:
            raise ValueError(f"Quest {quest_id} is not active (status={q.status.value})")
        q.status = QuestStatus.COMPLETED
        q.completed_hour = current_hour
        return q

    def fail_quest(self, quest_id: str) -> QuestEntry:
        q = self.quests[quest_id]
        q.status = QuestStatus.EXPIRED
        return q

    # ── consequence handlers ─────────────────────────────────────────
    def register_consequence(
        self,
        tag: str,
        handler: Callable[[QuestEntry], Dict],
    ) -> None:
        self._consequence_handlers[tag] = handler

    # ── tick ─────────────────────────────────────────────────────────
    def tick(self, current_hour: float) -> Dict[str, List]:
        """Check all active quests for expiry and near-deadline reminders.

        Returns ``{"expired": [...], "reminders": [...]}``.
        """
        expired_events: List[Dict] = []
        reminder_events: List[Dict] = []

        for q in list(self.quests.values()):
            if q.status != QuestStatus.ACTIVE:
                continue
            if q.deadline_hour is None:
                continue

            remaining = q.deadline_hour - current_hour

            # Expired?
            if remaining <= 0:
                q.status = QuestStatus.EXPIRED
                consequence_result = {}
                handler = self._consequence_handlers.get(q.timeout_consequence)
                if handler:
                    consequence_result = handler(q)
                expired_events.append({
                    "quest_id": q.quest_id,
                    "title": q.title,
                    "consequence": q.timeout_consequence,
                    "consequence_result": consequence_result,
                })
                continue

            # Reminders
            for reminder_threshold in q.reminder_hours:
                if remaining <= reminder_threshold and reminder_threshold not in q._reminders_sent:
                    q._reminders_sent.append(reminder_threshold)
                    reminder_events.append({
                        "quest_id": q.quest_id,
                        "title": q.title,
                        "hours_remaining": round(remaining, 2),
                        "reminder_threshold": reminder_threshold,
                    })

        return {"expired": expired_events, "reminders": reminder_events}

    # ── queries ──────────────────────────────────────────────────────
    def check_reminders(self, current_hour: float) -> List[Dict]:
        """Convenience: return only the reminder events from tick."""
        return self.tick(current_hour)["reminders"]

    def get_active_quests(self) -> List[QuestEntry]:
        return [q for q in self.quests.values() if q.status == QuestStatus.ACTIVE]

    def get_quest(self, quest_id: str) -> Optional[QuestEntry]:
        return self.quests.get(quest_id)

    def get_expired_quests(self) -> List[QuestEntry]:
        return [q for q in self.quests.values() if q.status == QuestStatus.EXPIRED]

    def to_dict(self) -> dict:
        """Serialize quest tracker for save/load."""
        return {
            "quests": {
                qid: {
                    "quest_id": q.quest_id,
                    "title": q.title,
                    "deadline_hour": q.deadline_hour,
                    "timeout_consequence": q.timeout_consequence,
                    "reminder_hours": q.reminder_hours,
                    "status": q.status.value,
                    "accepted_hour": q.accepted_hour,
                    "completed_hour": q.completed_hour,
                    "reminders_sent": list(q._reminders_sent),
                }
                for qid, q in self.quests.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuestTracker":
        """Deserialize quest tracker from a dict."""
        qt = cls()
        for qid, qd in data.get("quests", {}).items():
            entry = QuestEntry(
                quest_id=qd["quest_id"],
                title=qd["title"],
                deadline_hour=qd.get("deadline_hour"),
                timeout_consequence=qd.get("timeout_consequence", "quest_failed"),
                reminder_hours=qd.get("reminder_hours", [24.0, 8.0, 1.0]),
                status=QuestStatus(qd.get("status", "active")),
                accepted_hour=qd.get("accepted_hour", 0.0),
                completed_hour=qd.get("completed_hour"),
            )
            entry._reminders_sent = qd.get("reminders_sent", [])
            qt.quests[qid] = entry
        return qt
