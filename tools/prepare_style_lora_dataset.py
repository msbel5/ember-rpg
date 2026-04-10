#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def slugify(text: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "asset"


def load_names(path: Path) -> list[str]:
    names: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        names.append(slugify(line))
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a tiny LoRA dataset from selected generated assets")
    parser.add_argument("--names-file", required=True)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--token", default="ember-style")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = load_names(Path(args.names_file))
    metadata_path = out_dir / "metadata.jsonl"
    rows: list[dict[str, str]] = []

    for name in names:
        source = input_dir / f"{name}.png"
        if not source.exists():
            continue
        target = out_dir / source.name
        shutil.copy2(source, target)
        rows.append(
            {
                "file_name": target.name,
                "text": f"{args.token} dark-fantasy crpg item icon, {name.replace('_', ' ')}",
            }
        )

    metadata_path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=True) for row in rows),
        encoding="utf-8",
    )
    print(f"Prepared {len(rows)} training samples -> {out_dir}")
    print(f"Metadata -> {metadata_path}")


if __name__ == "__main__":
    main()
