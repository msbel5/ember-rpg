import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _load_json(name: str) -> dict:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def test_all_recipe_and_starting_equipment_items_exist_in_items_catalog() -> None:
    items = {item["id"] for item in _load_json("items.json")["items"]}
    recipes = _load_json("recipes.json")["recipes"]
    classes = _load_json("classes.json")["classes"]

    missing_recipe_ingredients = sorted(
        {
            ingredient["item_id"]
            for recipe in recipes
            for ingredient in recipe.get("ingredients", [])
            if ingredient["item_id"] not in items
        }
    )
    missing_recipe_products = sorted(
        {
            product["item_id"]
            for recipe in recipes
            for product in recipe.get("products", [])
            if product["item_id"] not in items
        }
    )
    missing_starting_equipment = sorted(
        {
            equipment["id"]
            for class_def in classes.values()
            for equipment in class_def.get("starting_equipment", [])
            if equipment["id"] not in items
        }
    )

    assert missing_recipe_ingredients == []
    assert missing_recipe_products == []
    assert missing_starting_equipment == []


def test_new_item_corpus_entries_keep_minimal_required_fields() -> None:
    required_fields = {"id", "name", "type", "rarity", "value", "weight", "description"}
    expected_new_ids = {
        "ale",
        "antidote",
        "antiseptic_tincture",
        "backpack",
        "bed",
        "belt",
        "bloodclot_poultice",
        "bloodthorn",
        "boar_meat",
        "boots",
        "bow",
        "bread",
        "chain_mail",
        "chair",
        "chamomile",
        "charcoal",
        "cloth",
        "coal",
        "daggers",
        "door",
        "dried_meat",
        "egg",
        "feather",
        "fever_tea",
        "field_bandage",
        "fire_bomb",
        "fish_fillet",
        "flour",
        "flux",
        "fruit",
        "ghost_lichen",
        "glass_vial",
        "gloves",
        "grain",
        "healing_potion",
        "healing_salve",
        "herb_cure",
        "herb_heal",
        "herbal_tea",
        "hide",
        "holy_water",
        "honey",
        "honey_cake",
        "horseshoe",
        "invisibility_potion",
        "iron_arrowhead",
        "iron_bar",
        "iron_dust",
        "iron_helm",
        "iron_nail",
        "iron_sword",
        "ironbark_tonic",
        "ladder",
        "leather",
        "leather_armor",
        "lockpick",
        "lyre",
        "mace",
        "mana_potion",
        "meat",
        "medicinal_broth",
        "moonflower",
        "mushroom",
        "mushroom_soup",
        "ogre_moss",
        "oil",
        "pain_suppressor",
        "plague_antidote",
        "poison_vial",
        "raw_fish",
        "resistance_potion",
        "restorative_stew",
        "roast_boar",
        "robes",
        "rope",
        "salt",
        "saltpeter",
        "satchel",
        "scroll_fireball",
        "shield",
        "sinew",
        "smoke_bomb",
        "speed_potion",
        "splint_brace",
        "spring_water",
        "staff",
        "steel_bar",
        "steel_dagger",
        "steel_sword",
        "stew",
        "stonecap",
        "strength_elixir",
        "surgical_kit",
        "table",
        "tanning_agent",
        "torch",
        "trail_rations",
        "vegetable",
        "water",
        "waterskin",
        "windleaf",
        "wood_plank",
        "wood_stick",
        "wooden_chest",
        "wooden_fence",
        "yeast",
    }
    catalog = {item["id"]: item for item in _load_json("items.json")["items"]}

    assert expected_new_ids <= set(catalog)
    for item_id in expected_new_ids:
        assert required_fields <= set(catalog[item_id])
