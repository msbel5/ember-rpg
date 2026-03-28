"""Stable seed derivation helpers for deterministic world simulation."""

from __future__ import annotations

import hashlib


def _stable_seed_from_text(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def stable_seed_from_parts(*parts: object) -> int:
    normalized = "::".join(str(part) for part in parts)
    return _stable_seed_from_text(normalized)


class WorldSeed:
    """Canonical deterministic seed with named sub-seed derivation."""

    def __init__(self, seed: int | str):
        if isinstance(seed, str):
            normalized = seed.strip()
            if normalized.isdigit() or (normalized.startswith("-") and normalized[1:].isdigit()):
                self._seed = int(normalized)
            else:
                self._seed = _stable_seed_from_text(normalized)
        else:
            self._seed = int(seed)

    @property
    def value(self) -> int:
        return self._seed

    def derive(self, label: str) -> int:
        return stable_seed_from_parts(self._seed, label)

    def terrain_seed(self) -> int:
        return self.derive("terrain")

    def settlement_seed(self) -> int:
        return self.derive("settlement")

    def npc_seed(self) -> int:
        return self.derive("npc")

    def quest_seed(self) -> int:
        return self.derive("quest")

    def economy_seed(self) -> int:
        return self.derive("economy")

    def weather_seed(self) -> int:
        return self.derive("weather")

    def history_seed(self) -> int:
        return self.derive("history")

    def __int__(self) -> int:
        return self._seed

    def __repr__(self) -> str:
        return f"WorldSeed({self._seed})"
