#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def score_item(path: Path) -> dict[str, float | str]:
    img = Image.open(path).convert("RGBA")
    width, height = img.size
    alpha = img.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return {"name": path.stem, "score": 0.0, "alpha_ratio": 0.0, "colors": 0, "entropy": 0.0}

    left, top, right, bottom = bbox
    bbox_area = max(1, (right - left) * (bottom - top))
    total_area = width * height
    alpha_ratio = bbox_area / total_area

    quant = img.convert("RGB").quantize(colors=64)
    colors = len(quant.getcolors(maxcolors=256) or [])
    entropy = img.convert("RGB").entropy()

    cx = (left + right) / 2.0 / width
    cy = (top + bottom) / 2.0 / height
    center_distance = math.sqrt((cx - 0.5) ** 2 + (cy - 0.5) ** 2)

    alpha_score = 1.0 - min(abs(alpha_ratio - 0.34) / 0.34, 1.0)
    color_score = clamp01(colors / 24.0)
    entropy_score = clamp01(entropy / 4.0)
    center_score = 1.0 - min(center_distance / 0.5, 1.0)
    size_score = clamp01(path.stat().st_size / 2200.0)

    score = (
        alpha_score * 0.28
        + color_score * 0.18
        + entropy_score * 0.24
        + center_score * 0.18
        + size_score * 0.12
    )
    return {
        "name": path.stem,
        "score": round(score, 4),
        "alpha_ratio": round(alpha_ratio, 4),
        "colors": colors,
        "entropy": round(entropy, 4),
        "bytes": path.stat().st_size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score generated item icons for first-pass curation")
    parser.add_argument("--folder", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-names", required=True)
    parser.add_argument("--top", type=int, default=24)
    args = parser.parse_args()

    folder = Path(args.folder)
    scored = []
    for path in sorted(folder.glob("*.png")):
        if path.name.endswith(".import"):
            continue
        scored.append(score_item(path))
    scored.sort(key=lambda row: (float(row["score"]), int(row["bytes"])), reverse=True)

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(scored, indent=2), encoding="utf-8")

    top_names = [str(row["name"]) for row in scored[: args.top]]
    out_names = Path(args.out_names)
    out_names.parent.mkdir(parents=True, exist_ok=True)
    out_names.write_text("\n".join(top_names) + "\n", encoding="utf-8")
    print(f"Scored {len(scored)} items -> {out_json}")
    print(f"Wrote top {len(top_names)} shortlist -> {out_names}")


if __name__ == "__main__":
    main()
