from __future__ import annotations

import shutil
from pathlib import Path


def main() -> None:
    repo_skill = Path(__file__).resolve().parents[1]
    home_skill = Path.home() / ".codex" / "skills" / repo_skill.name
    if home_skill.exists():
        shutil.rmtree(home_skill)
    shutil.copytree(repo_skill, home_skill)
    print(f"Synced {repo_skill} -> {home_skill}")


if __name__ == "__main__":
    main()
