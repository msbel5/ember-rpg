from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from engine.kernel.actor import ActorRecord

_INDEX_RE = re.compile(r"^(?P<base>.+?)\s+#(?P<index>\d+)$")


@dataclass(frozen=True)
class ActorQueryCandidate:
    actor: "ActorRecord"
    actor_id: str
    display_name: str
    actor_type: str
    role: str


@dataclass(frozen=True)
class ActorQueryResolution:
    actor: "ActorRecord | None" = None
    error: str | None = None


def resolve_live_actor_query(
    actors: dict[str, Any],
    query: str,
    *,
    include_player: bool = False,
    allow_dead: bool = True,
    actor_types: set[str] | None = None,
    predicate: Callable[["ActorRecord"], bool] | None = None,
) -> ActorQueryResolution:
    raw_query = str(query or "").strip()
    if not raw_query:
        return ActorQueryResolution()

    full_query = raw_query.lower()
    for candidate in _candidate_pool(
        actors,
        include_player=include_player,
        allow_dead=allow_dead,
        actor_types=actor_types,
        predicate=predicate,
    ):
        if full_query == candidate.actor_id.lower():
            return ActorQueryResolution(actor=candidate.actor)

    base_query, requested_index = _parse_indexed_query(raw_query)
    normalized_query = base_query.lower().strip()
    exact_matches = _sorted_candidates(
        candidate
        for candidate in _candidate_pool(
            actors,
            include_player=include_player,
            allow_dead=allow_dead,
            actor_types=actor_types,
            predicate=predicate,
        )
        if normalized_query == candidate.display_name.lower()
    )
    partial_matches = _sorted_candidates(
        candidate
        for candidate in _candidate_pool(
            actors,
            include_player=include_player,
            allow_dead=allow_dead,
            actor_types=actor_types,
            predicate=predicate,
        )
        if normalized_query in candidate.display_name.lower() or normalized_query.replace(" ", "_") in candidate.actor_id.lower()
    )

    if requested_index is not None:
        candidates = exact_matches or partial_matches
        if 1 <= requested_index <= len(candidates):
            return ActorQueryResolution(actor=candidates[requested_index - 1].actor)
        if candidates:
            return ActorQueryResolution(error=_ambiguity_message(base_query, candidates))
        return ActorQueryResolution()

    if len(exact_matches) == 1:
        return ActorQueryResolution(actor=exact_matches[0].actor)
    if len(exact_matches) > 1:
        return ActorQueryResolution(error=_ambiguity_message(base_query, exact_matches))
    if len(partial_matches) == 1:
        return ActorQueryResolution(actor=partial_matches[0].actor)
    if len(partial_matches) > 1:
        return ActorQueryResolution(error=_ambiguity_message(base_query, partial_matches))
    return ActorQueryResolution()


def _candidate_pool(
    actors: dict[str, Any],
    *,
    include_player: bool,
    allow_dead: bool,
    actor_types: set[str] | None,
    predicate: Callable[["ActorRecord"], bool] | None,
) -> list[ActorQueryCandidate]:
    candidates: list[ActorQueryCandidate] = []
    allowed_types = {item.lower() for item in actor_types} if actor_types else None
    for actor_id, actor in actors.items():
        identity = getattr(actor, "identity", None)
        if identity is None:
            continue
        resolved_id = str(actor_id).strip()
        if not resolved_id:
            continue
        if resolved_id == "player" and not include_player:
            continue
        if not allow_dead and not bool(getattr(actor, "alive", True)):
            continue
        actor_type = str(getattr(identity, "actor_type", "")).strip().lower()
        if allowed_types is not None and actor_type not in allowed_types:
            continue
        if predicate is not None and not predicate(actor):
            continue
        display_name = str(getattr(identity, "display_name", "")).strip()
        if not display_name:
            continue
        role = str(getattr(actor, "raw_payload", {}).get("role", "")).strip().lower()
        candidates.append(
            ActorQueryCandidate(
                actor=actor,
                actor_id=resolved_id,
                display_name=display_name,
                actor_type=actor_type or "actor",
                role=role or actor_type or "actor",
            )
        )
    return candidates


def _parse_indexed_query(query: str) -> tuple[str, int | None]:
    match = _INDEX_RE.match(query.strip())
    if match is None:
        return query.strip(), None
    return match.group("base").strip(), max(1, int(match.group("index")))


def _sorted_candidates(candidates: Any) -> list[ActorQueryCandidate]:
    return sorted(list(candidates), key=lambda item: (item.display_name.lower(), item.actor_id.lower()))


def _ambiguity_message(query: str, candidates: list[ActorQueryCandidate]) -> str:
    summary = "; ".join(
        f"{index}. {candidate.display_name} ({candidate.actor_type}/{candidate.role}, {_short_actor_id(candidate.actor_id)})"
        for index, candidate in enumerate(candidates, start=1)
    )
    return (
        f"Multiple actors match '{query}': {summary}. "
        f"Use '{query} #<index>' or the full actor id."
    )


def _short_actor_id(actor_id: str) -> str:
    return actor_id if len(actor_id) <= 10 else f"...{actor_id[-8:]}"


__all__ = ["ActorQueryResolution", "resolve_live_actor_query"]
