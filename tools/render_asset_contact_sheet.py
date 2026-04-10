#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def slugify(text: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "asset"


def load_names(names_file: Path | None) -> set[str]:
    names: set[str] = set()
    if not names_file or not names_file.exists():
        return names
    for raw_line in names_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        names.add(slugify(line))
    return names


def discover_images(folder: Path, names: set[str], limit: int | None) -> list[Path]:
    files = sorted(p for p in folder.glob("*.png") if p.is_file() and not p.name.endswith(".import"))
    if names:
        files = [p for p in files if slugify(p.stem) in names]
    if limit is not None:
        files = files[:limit]
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a simple contact sheet for generated assets")
    parser.add_argument("--folder", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--names-file")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--cols", type=int, default=6)
    parser.add_argument("--thumb", type=int, default=96)
    parser.add_argument("--label-height", type=int, default=20)
    args = parser.parse_args()

    folder = Path(args.folder)
    out_path = Path(args.out)
    names = load_names(Path(args.names_file)) if args.names_file else set()
    images = discover_images(folder, names, args.limit)
    if not images:
        raise SystemExit(f"No images found in {folder}")

    cols = max(1, args.cols)
    thumb = max(32, args.thumb)
    label_height = max(14, args.label_height)
    rows = (len(images) + cols - 1) // cols
    padding = 12
    width = cols * (thumb + padding) + padding
    height = rows * (thumb + label_height + padding) + padding
    sheet = Image.new("RGBA", (width, height), (18, 15, 24, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, image_path in enumerate(images):
        row = index // cols
        col = index % cols
        x = padding + col * (thumb + padding)
        y = padding + row * (thumb + label_height + padding)
        img = Image.open(image_path).convert("RGBA")
        if img.width < thumb and img.height < thumb:
            scale = max(1, min(thumb // max(1, img.width), thumb // max(1, img.height)))
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        else:
            img.thumbnail((thumb, thumb), Image.NEAREST)
        slot = Image.new("RGBA", (thumb, thumb), (34, 29, 40, 255))
        px = (thumb - img.width) // 2
        py = (thumb - img.height) // 2
        slot.alpha_composite(img, (px, py))
        sheet.alpha_composite(slot, (x, y))
        draw.rectangle((x, y, x + thumb, y + thumb), outline=(194, 151, 84, 255), width=1)
        draw.text((x, y + thumb + 4), image_path.stem[:20], fill=(238, 230, 217, 255), font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    print(f"Wrote contact sheet -> {out_path}")


if __name__ == "__main__":
    main()
