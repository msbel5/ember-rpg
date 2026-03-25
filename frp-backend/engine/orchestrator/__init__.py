"""
Scene Orchestrator — coordinates MAP, ENTITIES, NARRATIVE in order.
Each concern is isolated. DM_NARRATOR never modifies state.
MAP_GENERATOR never narrates.
"""
import asyncio
import json
import random
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional
from datetime import datetime


@dataclass
class SceneRequest:
    session_id: str
    location: str
    location_type: str = "town"  # town, dungeon, wilderness, cave, tavern
    time_of_day: str = "morning"  # morning, afternoon, evening, night
    player_name: str = "Adventurer"
    player_level: int = 1
    is_first_visit: bool = True
    world_context: str = ""
    npc_context: str = ""


@dataclass
class TileMapData:
    width: int
    height: int
    tiles: list  # 2D list of tile type strings
    rooms: list  # list of room dicts
    connections: list  # list of connection dicts
    seed: int


@dataclass
class PlacedEntity:
    id: str
    entity_type: str  # npc, item, enemy, container, interactive
    template: str
    position: list  # [x, y]
    name: str = ""
    is_hostile: bool = False
    is_interactive: bool = True
    context_actions: list = field(default_factory=list)  # ["examine", "talk", "trade"]


@dataclass
class NarrativeChunk:
    text: str
    delay_ms: int = 0
    reveal: Optional[dict] = None  # {"type": "npc", "id": "guard_1"} or None


@dataclass
class SceneResponse:
    session_id: str
    location: str
    map_data: dict
    entities: dict  # {"npcs": [...], "items": [...], "enemies": [...]}
    narrative_stream: list  # list of NarrativeChunk dicts
    available_actions: list
    scene_type: str
    timestamp: str


class MapGenerator:
    """Deterministic map generation. No LLM involved."""

    TILE_SETS = {
        "town": {
            "ground": ["cobblestone", "dirt_path", "grass"],
            "walls": ["stone_wall", "wooden_fence"],
            "special": ["door", "window", "chest", "barrel"]
        },
        "dungeon": {
            "ground": ["stone_floor", "cracked_stone", "wet_stone"],
            "walls": ["dungeon_wall", "reinforced_wall"],
            "special": ["torch_wall", "secret_door", "pit", "treasure_chest"]
        },
        "tavern": {
            "ground": ["wooden_floor", "rug"],
            "walls": ["wooden_wall", "stone_wall"],
            "special": ["fireplace", "table", "bar_counter", "stairs"]
        },
        "wilderness": {
            "ground": ["grass", "dirt", "mud", "rocky_ground"],
            "walls": ["tree", "large_rock", "cliff"],
            "special": ["campfire_pit", "fallen_log", "cave_entrance"]
        },
        "cave": {
            "ground": ["cave_floor", "wet_cave_floor", "gravel"],
            "walls": ["cave_wall", "stalactite"],
            "special": ["glowing_mushroom", "underground_pool", "crystal_formation"]
        }
    }

    ROOM_TEMPLATES = {
        "town": [
            {"id": "market", "name": "Market Square", "type": "outdoor", "bounds_rel": [0.3, 0.3, 0.7, 0.7]},
            {"id": "tavern_building", "name": "The Rusty Anchor Tavern", "type": "building", "bounds_rel": [0.1, 0.1, 0.4, 0.4]},
            {"id": "docks", "name": "Harbor Docks", "type": "water_edge", "bounds_rel": [0.0, 0.7, 1.0, 1.0]},
            {"id": "north_gate", "name": "Town Gate", "type": "entrance", "bounds_rel": [0.4, 0.0, 0.6, 0.1]},
        ],
        "dungeon": [
            {"id": "entrance_hall", "name": "Entrance Hall", "type": "corridor", "bounds_rel": [0.3, 0.0, 0.7, 0.3]},
            {"id": "main_chamber", "name": "Main Chamber", "type": "chamber", "bounds_rel": [0.2, 0.3, 0.8, 0.7]},
            {"id": "side_passage", "name": "Side Passage", "type": "corridor", "bounds_rel": [0.0, 0.3, 0.2, 0.6]},
            {"id": "boss_room", "name": "Inner Sanctum", "type": "boss_chamber", "bounds_rel": [0.3, 0.7, 0.7, 1.0]},
        ],
        "tavern": [
            {"id": "common_room", "name": "Common Room", "type": "interior", "bounds_rel": [0.1, 0.1, 0.9, 0.7]},
            {"id": "bar", "name": "Bar Counter", "type": "interior", "bounds_rel": [0.1, 0.1, 0.4, 0.3]},
            {"id": "back_room", "name": "Back Room", "type": "private", "bounds_rel": [0.7, 0.1, 0.9, 0.5]},
            {"id": "cellar_stairs", "name": "Cellar Stairs", "type": "transition", "bounds_rel": [0.8, 0.6, 0.9, 0.7]},
        ],
        "wilderness": [
            {"id": "clearing", "name": "Forest Clearing", "type": "outdoor", "bounds_rel": [0.3, 0.3, 0.7, 0.7]},
            {"id": "path_north", "name": "Northern Path", "type": "path", "bounds_rel": [0.45, 0.0, 0.55, 0.35]},
            {"id": "dense_forest", "name": "Dense Forest", "type": "obstacle", "bounds_rel": [0.0, 0.0, 0.3, 1.0]},
        ],
        "cave": [
            {"id": "cave_entrance", "name": "Cave Entrance", "type": "entrance", "bounds_rel": [0.4, 0.0, 0.6, 0.2]},
            {"id": "main_cavern", "name": "Main Cavern", "type": "chamber", "bounds_rel": [0.2, 0.2, 0.8, 0.8]},
            {"id": "crystal_grotto", "name": "Crystal Grotto", "type": "special", "bounds_rel": [0.6, 0.5, 0.9, 0.9]},
        ]
    }

    def generate(self, location_type: str, width: int = 20, height: int = 15, seed: int = None) -> TileMapData:
        if seed is None:
            seed = random.randint(1000, 9999)
        rng = random.Random(seed)

        tile_set = self.TILE_SETS.get(location_type, self.TILE_SETS["town"])
        ground_tiles = tile_set["ground"]

        # Generate base tile grid
        tiles = []
        for row in range(height):
            tile_row = []
            for col in range(width):
                tile = rng.choices(ground_tiles, weights=[70, 20, 10][:len(ground_tiles)])[0]
                tile_row.append(tile)
            tiles.append(tile_row)

        # Generate rooms
        room_templates = self.ROOM_TEMPLATES.get(location_type, self.ROOM_TEMPLATES["town"])
        rooms = []
        for rt in room_templates:
            bounds = [
                int(rt["bounds_rel"][0] * width),
                int(rt["bounds_rel"][1] * height),
                int(rt["bounds_rel"][2] * width),
                int(rt["bounds_rel"][3] * height),
            ]
            rooms.append({
                "id": rt["id"],
                "name": rt["name"],
                "type": rt["type"],
                "bounds": bounds
            })

        # Build connections
        connections = []
        for i in range(len(rooms) - 1):
            connections.append({
                "from": rooms[i]["id"],
                "to": rooms[i+1]["id"],
                "type": "passage"
            })

        return TileMapData(
            width=width, height=height,
            tiles=tiles, rooms=rooms, connections=connections,
            seed=seed
        )


class EntityPlacer:
    """Deterministic entity placement based on location type + templates."""

    NPC_TEMPLATES_BY_LOCATION = {
        "town": ["merchant", "guard", "innkeeper", "quest_giver", "beggar"],
        "dungeon": ["skeleton_guard", "dungeon_prisoner", "trapped_adventurer"],
        "tavern": ["innkeeper", "merchant", "bard", "drunk_patron", "mysterious_stranger"],
        "wilderness": ["traveling_merchant", "ranger", "bandit"],
        "cave": ["cave_hermit", "goblin_scout"],
    }

    ITEM_TEMPLATES_BY_LOCATION = {
        "town": ["notice_board", "market_stall", "barrel", "crate", "well"],
        "dungeon": ["treasure_chest", "torch", "skeleton_remains", "locked_door"],
        "tavern": ["fireplace", "notice_board", "locked_chest", "bookshelf"],
        "wilderness": ["campfire_remains", "abandoned_cart", "mysterious_altar"],
        "cave": ["glowing_crystal", "old_bones", "treasure_cache"],
    }

    ENEMY_TEMPLATES_BY_LOCATION = {
        "dungeon": ["skeleton", "zombie", "giant_spider", "orc"],
        "wilderness": ["wolf", "bandit", "goblin"],
        "cave": ["cave_bat", "cave_troll", "goblin"],
        "town": [],  # peaceful
        "tavern": [],  # peaceful
    }

    CONTEXT_ACTIONS = {
        "npc": {
            "merchant": ["examine", "talk", "trade"],
            "guard": ["examine", "talk"],
            "innkeeper": ["examine", "talk", "trade", "rest"],
            "quest_giver": ["examine", "talk"],
            "default": ["examine", "talk"],
        },
        "item": {
            "treasure_chest": ["examine", "open", "lock_pick"],
            "notice_board": ["examine", "read"],
            "barrel": ["examine", "open", "kick"],
            "default": ["examine", "pick_up"],
        },
        "enemy": {
            "default": ["examine", "attack", "flee"],
        },
        "interactive": {
            "default": ["examine", "interact"],
        }
    }

    def place(self, location_type: str, map_data: TileMapData, max_npcs: int = 4, seed: int = None) -> dict:
        rng = random.Random(seed or map_data.seed + 1)
        width, height = map_data.width, map_data.height
        used_positions = set()

        def random_pos():
            for _ in range(100):
                x, y = rng.randint(1, width-2), rng.randint(1, height-2)
                if (x, y) not in used_positions:
                    used_positions.add((x, y))
                    return [x, y]
            return [width//2, height//2]

        npc_templates = self.NPC_TEMPLATES_BY_LOCATION.get(location_type, ["villager"])
        item_templates = self.ITEM_TEMPLATES_BY_LOCATION.get(location_type, ["barrel"])
        enemy_templates = self.ENEMY_TEMPLATES_BY_LOCATION.get(location_type, [])

        npcs = []
        chosen_npcs = rng.sample(npc_templates, min(max_npcs, len(npc_templates)))
        for i, template in enumerate(chosen_npcs):
            actions = self.CONTEXT_ACTIONS["npc"].get(template, self.CONTEXT_ACTIONS["npc"]["default"])
            npcs.append(PlacedEntity(
                id=f"{template}_{i+1}",
                entity_type="npc",
                template=template,
                position=random_pos(),
                name=template.replace("_", " ").title(),
                is_hostile=False,
                context_actions=actions
            ).__dict__)

        items = []
        chosen_items = rng.sample(item_templates, min(3, len(item_templates)))
        for i, template in enumerate(chosen_items):
            actions = self.CONTEXT_ACTIONS["item"].get(template, self.CONTEXT_ACTIONS["item"]["default"])
            items.append(PlacedEntity(
                id=f"{template}_{i+1}",
                entity_type="item",
                template=template,
                position=random_pos(),
                name=template.replace("_", " ").title(),
                is_hostile=False,
                context_actions=actions
            ).__dict__)

        enemies = []
        if enemy_templates:
            num_enemies = rng.randint(1, 3)
            chosen_enemies = [rng.choice(enemy_templates) for _ in range(num_enemies)]
            for i, template in enumerate(chosen_enemies):
                actions = self.CONTEXT_ACTIONS["enemy"]["default"]
                enemies.append(PlacedEntity(
                    id=f"{template}_{i+1}",
                    entity_type="enemy",
                    template=template,
                    position=random_pos(),
                    name=template.replace("_", " ").title(),
                    is_hostile=True,
                    context_actions=actions
                ).__dict__)

        return {"npcs": npcs, "items": items, "enemies": enemies}


class DMNarrator:
    """LLM-powered scene narrative. NEVER modifies game state."""

    SCENE_SYSTEM_PROMPT = """You are the Dungeon Master for Ember RPG, a dark fantasy tabletop RPG.
Your role: narrate the scene as a player enters it. Build atmosphere.

Rules:
- Start with a vivid opening sentence that sets the mood
- Reveal key map elements naturally (market, guards, items)
- Keep total narrative to 3-5 sentences
- Each sentence should optionally reveal a specific entity (use [REVEAL:entity_id] marker)
- Use second person: "Before you..." "You see..." "To your left..."
- Match tone to location: tense in dungeons, lively in towns, eerie in caves
- Reference world state context when relevant
- End with a subtle hook or unresolved detail that invites exploration"""

    FALLBACK_NARRATIVES = {
        "town": "The town square bustles with morning activity. Merchants call out their wares while guards patrol the cobblestone streets. [REVEAL:merchant_1] A weathered notice board near the market square catches your eye. [REVEAL:notice_board_1]",
        "dungeon": "Cold air greets you as you descend into the darkness. [REVEAL:torch_1] Torchlight flickers off damp stone walls, revealing a corridor stretching deeper underground. The silence is broken only by distant dripping water — and something else. Something breathing.",
        "tavern": "Warm firelight and the smell of ale wash over you. [REVEAL:innkeeper_1] The innkeeper looks up from polishing a glass, nodding in greeting. A half-dozen patrons occupy the common room, conversations dropping to murmurs as you enter.",
        "wilderness": "The forest path widens into a clearing bathed in diffused light. [REVEAL:traveling_merchant_1] Birdsong fills the air, though you notice it stops suddenly near the treeline to the east. The undergrowth shows signs of recent disturbance.",
        "cave": "Darkness swallows you as you enter the cave mouth. [REVEAL:glowing_crystal_1] Faintly glowing crystals embedded in the rock provide just enough light to navigate. The air is cold and carries the faint smell of sulfur.",
    }

    def __init__(self):
        self._llm = None

    def _get_llm(self):
        if self._llm is None:
            from engine.llm import get_llm_router
            self._llm = get_llm_router()
        return self._llm

    def narrate(self, request: SceneRequest, entities: dict) -> str:
        """Generate scene narrative. Falls back to template if LLM unavailable."""
        llm = self._get_llm()

        # Build entity list for DM
        npc_names = [e["name"] for e in entities.get("npcs", [])]
        item_names = [e["name"] for e in entities.get("items", [])]
        enemy_names = [e["name"] for e in entities.get("enemies", [])]
        npc_ids = [e["id"] for e in entities.get("npcs", [])]
        item_ids = [e["id"] for e in entities.get("items", [])]

        user_prompt = f"""Scene: {request.location} ({request.location_type})
Time of day: {request.time_of_day}
Player: {request.player_name}, level {request.player_level}
First visit: {request.is_first_visit}

Present entities:
- NPCs: {', '.join(npc_names) if npc_names else 'none'}
  IDs: {', '.join(npc_ids) if npc_ids else 'none'}
- Items/Interactables: {', '.join(item_names) if item_names else 'none'}
  IDs: {', '.join(item_ids) if item_ids else 'none'}
- Enemies: {', '.join(enemy_names) if enemy_names else 'none'}

{f'World context: {request.world_context}' if request.world_context else ''}

Narrate the scene. Use [REVEAL:entity_id] markers when you first mention an entity.
Example: "A gruff merchant eyes you suspiciously. [REVEAL:merchant_1]"
Keep to 3-5 sentences total."""

        result = llm.narrative(self.SCENE_SYSTEM_PROMPT, user_prompt, important=False)
        if result:
            return result

        return self.FALLBACK_NARRATIVES.get(request.location_type,
            f"You arrive at {request.location}. The area seems quiet for now.")

    def parse_narrative_stream(self, narrative: str, entities: dict) -> list:
        """
        Parse narrative text into NarrativeChunk list with reveal triggers.
        Splits on sentences, extracts [REVEAL:id] markers.
        """
        import re
        sentences = re.split(r'(?<=[.!?])\s+', narrative.strip())
        chunks = []
        delay = 0

        entity_map = {}
        for e_list in [entities.get("npcs", []), entities.get("items", []), entities.get("enemies", [])]:
            for e in e_list:
                entity_map[e["id"]] = e["entity_type"]

        for sentence in sentences:
            reveal = None
            reveal_match = re.search(r'\[REVEAL:([^\]]+)\]', sentence)
            if reveal_match:
                entity_id = reveal_match.group(1)
                sentence = re.sub(r'\s*\[REVEAL:[^\]]+\]', '', sentence).strip()
                entity_type = entity_map.get(entity_id, "unknown")
                reveal = {"type": entity_type, "id": entity_id}

            if sentence:
                chunks.append({
                    "text": sentence,
                    "delay_ms": delay,
                    "reveal": reveal
                })
                delay += 2000  # 2 seconds between sentences

        return chunks


class SceneOrchestrator:
    """Coordinates MAP_GENERATOR → ENTITY_PLACER → DM_NARRATOR."""

    def __init__(self):
        self.map_generator = MapGenerator()
        self.entity_placer = EntityPlacer()
        self.dm_narrator = DMNarrator()

    def enter_scene(self, request: SceneRequest) -> SceneResponse:
        """
        Main orchestration flow:
        1. Generate map (deterministic)
        2. Place entities (deterministic)
        3. Generate narrative (LLM → fallback)
        4. Parse narrative into streaming chunks
        5. Return complete SceneResponse
        """
        # Step 1: Map
        map_data = self.map_generator.generate(request.location_type)

        # Step 2: Entities
        entities = self.entity_placer.place(request.location_type, map_data)

        # Step 3: Narrative
        narrative_text = self.dm_narrator.narrate(request, entities)

        # Step 4: Parse into stream
        narrative_stream = self.dm_narrator.parse_narrative_stream(narrative_text, entities)

        # Step 5: Available actions
        available_actions = ["examine", "move", "look_around"]
        if entities["npcs"]:
            available_actions.extend(["talk", "trade"])
        if entities["enemies"]:
            available_actions.append("attack")

        # Deduplicate
        available_actions = list(dict.fromkeys(available_actions))

        return SceneResponse(
            session_id=request.session_id,
            location=request.location,
            map_data={
                "width": map_data.width,
                "height": map_data.height,
                "tiles": map_data.tiles,
                "rooms": map_data.rooms,
                "connections": map_data.connections,
                "seed": map_data.seed,
            },
            entities=entities,
            narrative_stream=narrative_stream,
            available_actions=available_actions,
            scene_type=request.location_type,
            timestamp=datetime.now().isoformat()
        )

    async def enter_scene_streaming(self, request: SceneRequest) -> AsyncGenerator[str, None]:
        """
        SSE streaming version.
        Yields JSON lines for each event:
        - map_ready event first
        - narrative chunks in order
        - entities_ready event last
        """
        # Generate everything synchronously first
        map_data = self.map_generator.generate(request.location_type)
        entities = self.entity_placer.place(request.location_type, map_data)
        narrative_text = self.dm_narrator.narrate(request, entities)
        narrative_stream = self.dm_narrator.parse_narrative_stream(narrative_text, entities)

        # Yield map data first (Godot can start rendering background)
        yield json.dumps({
            "event": "map_ready",
            "data": {
                "width": map_data.width,
                "height": map_data.height,
                "tiles": map_data.tiles,
                "rooms": map_data.rooms,
                "connections": map_data.connections,
                "seed": map_data.seed,
            }
        }) + "\n"

        # Yield narrative chunks with reveals
        for chunk in narrative_stream:
            yield json.dumps({
                "event": "narrative",
                "data": chunk
            }) + "\n"
            await asyncio.sleep(0)  # yield control

        # Yield entities (now all revealed)
        yield json.dumps({
            "event": "entities_ready",
            "data": {
                "npcs": entities["npcs"],
                "items": entities["items"],
                "enemies": entities["enemies"],
            }
        }) + "\n"

        # Yield scene complete
        available_actions = ["examine", "move", "look_around"]
        if entities["npcs"]:
            available_actions.extend(["talk", "trade"])
        if entities["enemies"]:
            available_actions.append("attack")
        available_actions = list(dict.fromkeys(available_actions))

        yield json.dumps({
            "event": "scene_complete",
            "data": {
                "session_id": request.session_id,
                "location": request.location,
                "scene_type": request.location_type,
                "available_actions": available_actions,
                "timestamp": datetime.now().isoformat()
            }
        }) + "\n"
