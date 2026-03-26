"""Shared LLM-backed narration builders for API and terminal clients."""
from __future__ import annotations

import re
from typing import Callable, Optional

from .router import get_llm_router
from .settings import get_live_model_name

GAME_NARRATOR_SYSTEM_PROMPT = (
    "You are the Dungeon Master for Ember RPG, a grounded dark-fantasy RPG. "
    "Respect the supplied game state and mechanics exactly; never invent extra outcomes "
    "or contradict deterministic results. Write concise second-person narration with a "
    "consistent, low-flourish tone. For NPC dialogue, let the NPC speak directly. For "
    "ambiguous input, acknowledge the uncertainty inside the fiction instead of claiming "
    "mechanics that did not happen. Use 2-4 sentences. No markdown headers."
)


def build_game_narrator() -> Callable[[str], Optional[str]]:
    llm_router = get_llm_router()

    def _llm(prompt: str) -> Optional[str]:
        result = llm_router.complete(
            messages=[
                {"role": "system", "content": GAME_NARRATOR_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model=get_live_model_name(),
        )
        if result:
            result = re.sub(r"^#+\s+[^\n]*\n+", "", result, flags=re.MULTILINE).strip()
        return result

    return _llm
