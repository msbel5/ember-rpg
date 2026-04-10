#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


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
    parser = argparse.ArgumentParser(description="Build a style anchor board from selected generated assets")
    parser.add_argument("--folder", required=True)
    parser.add_argument("--names-file", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cols", type=int, default=5)
    parser.add_argument("--tile", type=int, default=192)
    args = parser.parse_args()

    folder = Path(args.folder)
    names = load_names(Path(args.names_file))
    images: list[Path] = []
    for name in names:
        candidate = folder / f"{name}.png"
        if candidate.exists():
            images.append(candidate)
    if not images:
        raise SystemExit("No selected images found.")

    cols = max(1, args.cols)
    tile = max(64, args.tile)
    rows = (len(images) + cols - 1) // cols
    padding = 16
    width = cols * (tile + padding) + padding
    height = rows * (tile + padding) + padding
    board = Image.new("RGBA", (width, height), (22, 18, 27, 255))
    draw = ImageDraw.Draw(board)

    for index, image_path in enumerate(images):
        row = index // cols
        col = index % cols
        x = padding + col * (tile + padding)
        y = padding + row * (tile + padding)
        img = Image.open(image_path).convert("RGBA")
        img.thumbnail((tile, tile), Image.NEAREST)
        slot = Image.new("RGBA", (tile, tile), (38, 31, 42, 255))
        px = (tile - img.width) // 2
        py = (tile - img.height) // 2
        slot.alpha_composite(img, (px, py))
        board.alpha_composite(slot, (x, y))
        draw.rectangle((x, y, x + tile, y + tile), outline=(194, 151, 84, 255), width=2)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    board.save(out_path)
    print(f"Wrote style anchor -> {out_path}")


if __name__ == "__main__":
    main()
