#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "asset"


def infer_subject(item_id: str, item_type: str, description: str) -> str:
    haystack = f"{item_id} {item_type} {description}".lower()
    buckets = [
        ("sword", ["sword", "blade", "rapier", "scimitar", "sabre", "saber"]),
        ("axe", ["axe", "hatchet"]),
        ("hammer", ["hammer", "maul", "mace", "flail", "morningstar"]),
        ("polearm", ["spear", "pike", "halberd", "lance", "trident"]),
        ("bow", ["bow", "crossbow", "arrow", "bolt"]),
        ("staff", ["staff", "wand", "rod"]),
        ("shield", ["shield", "buckler"]),
        ("armor", ["armor", "armour", "plate", "mail", "robe", "cloak", "boots", "helm", "helmet", "gauntlet", "gloves", "greaves", "belt"]),
        ("potion", ["potion", "elixir", "flask", "vial", "brew", "tea", "tincture"]),
        ("scroll", ["scroll", "tome", "book", "journal", "map", "page", "writ"]),
        ("jewel", ["ring", "amulet", "gem", "crystal", "shard", "brooch", "bracelet", "circlet", "pendant"]),
        ("material", ["ingot", "ore", "hide", "pelt", "cloth", "essence", "heart", "fang", "claw", "bone", "meat", "bark", "scale", "mushroom", "herb", "powder"]),
        ("currency", ["coin", "token", "seal", "bar"]),
        ("tool", ["tools", "kit", "supplies", "rope", "torch", "waterskin", "backpack", "chest", "chair", "table", "bed"]),
    ]
    for subject, keywords in buckets:
        if any(keyword in haystack for keyword in keywords):
            return subject
    return item_type or "misc"


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a diverse shortlist of generated items for style review")
    parser.add_argument("--scores-json", required=True)
    parser.add_argument("--items-json", required=True)
    parser.add_argument("--out-names", required=True)
    parser.add_argument("--target", type=int, default=28)
    args = parser.parse_args()

    scores = json.loads(Path(args.scores_json).read_text(encoding="utf-8"))
    items_payload = json.loads(Path(args.items_json).read_text(encoding="utf-8"))
    item_map = {slugify(item.get("id", "")): item for item in items_payload.get("items", []) if isinstance(item, dict)}

    ranked: list[dict[str, str | float]] = []
    buckets: dict[str, list[dict[str, str | float]]] = defaultdict(list)
    for row in scores:
        item_id = slugify(str(row.get("name", "")))
        item = item_map.get(item_id)
        if item is None:
            continue
        item_type = slugify(str(item.get("type", "misc")))
        subject = infer_subject(item_id, item_type, str(item.get("description", "")))
        bucket = f"{item_type}:{subject}"
        enriched = {
            "name": item_id,
            "bucket": bucket,
            "score": float(row.get("score", 0.0)),
            "rarity": str(item.get("rarity", "COMMON")),
        }
        buckets[bucket].append(enriched)
        ranked.append(enriched)

    for entries in buckets.values():
        entries.sort(key=lambda row: (row["score"], row["rarity"]), reverse=True)
    ranked.sort(key=lambda row: (row["score"], row["rarity"]), reverse=True)

    selected: list[str] = []
    used = set()

    bucket_keys = sorted(buckets.keys(), key=lambda key: max(float(row["score"]) for row in buckets[key]), reverse=True)
    while len(selected) < args.target:
        progressed = False
        for bucket in bucket_keys:
            while buckets[bucket]:
                candidate = buckets[bucket].pop(0)
                name = str(candidate["name"])
                if name in used:
                    continue
                selected.append(name)
                used.add(name)
                progressed = True
                break
            if len(selected) >= args.target:
                break
        if not progressed:
            break

    if len(selected) < args.target:
        for row in ranked:
            name = str(row["name"])
            if name in used:
                continue
            selected.append(name)
            used.add(name)
            if len(selected) >= args.target:
                break

    out_path = Path(args.out_names)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(selected) + "\n", encoding="utf-8")
    print(f"Wrote {len(selected)} selected ids -> {out_path}")


if __name__ == "__main__":
    main()
