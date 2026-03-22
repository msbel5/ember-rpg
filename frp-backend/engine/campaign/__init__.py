"""
Ember RPG - Phase 6: Campaign Generator
Procedural story arcs, quest chains, and world events.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable
from enum import Enum
import random


class QuestStatus(Enum):
    """Current state of a quest."""
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class QuestType(Enum):
    """Category of quest."""
    KILL = "kill"           # Eliminate target
    FETCH = "fetch"         # Retrieve item
    ESCORT = "escort"       # Protect NPC
    EXPLORE = "explore"     # Visit location
    DIALOGUE = "dialogue"   # Speak to someone
    SURVIVE = "survive"     # Survive N rounds


class EventType(Enum):
    """Campaign world event types."""
    AMBUSH = "ambush"
    DISCOVERY = "discovery"
    NPC_ENCOUNTER = "npc_encounter"
    WEATHER = "weather"
    PLOT_TWIST = "plot_twist"
    REWARD = "reward"
    TRAP = "trap"


@dataclass
class QuestObjective:
    """
    A single objective within a quest.

    Attributes:
        description: Human-readable objective text
        target: What to kill/fetch/find
        required_count: How many (for kill/fetch)
        current_count: Progress counter
        completed: Whether this objective is done
    """
    description: str
    target: str = ""
    required_count: int = 1
    current_count: int = 0
    completed: bool = False

    def progress(self, amount: int = 1) -> bool:
        """Advance progress. Returns True if just completed."""
        if self.completed:
            return False
        self.current_count = min(self.current_count + amount, self.required_count)
        if self.current_count >= self.required_count:
            self.completed = True
            return True
        return False

    def progress_text(self) -> str:
        """Return progress as 'X/Y' string."""
        return f"{self.current_count}/{self.required_count}"


@dataclass
class Quest:
    """
    A quest with objectives, rewards, and narrative.

    Attributes:
        id: Unique quest identifier
        title: Quest title
        description: Quest backstory and goal
        quest_type: Quest category
        giver: NPC name who gives the quest
        objectives: List of objectives to complete
        rewards: Gold, XP, and item rewards
        status: Current quest state
        location: Where the quest takes place
        difficulty: 1-5 difficulty rating
    """
    id: str
    title: str
    description: str
    quest_type: QuestType
    giver: str
    objectives: List[QuestObjective] = field(default_factory=list)
    rewards: Dict = field(default_factory=lambda: {"gold": 50, "xp": 100})
    status: QuestStatus = QuestStatus.AVAILABLE
    location: str = "Unknown"
    difficulty: int = 1

    def is_complete(self) -> bool:
        """Return True if all objectives are completed."""
        return all(obj.completed for obj in self.objectives)

    def activate(self) -> None:
        """Mark quest as active."""
        if self.status == QuestStatus.AVAILABLE:
            self.status = QuestStatus.ACTIVE

    def complete(self) -> Dict:
        """Mark quest completed and return rewards."""
        self.status = QuestStatus.COMPLETED
        return self.rewards

    def fail(self) -> None:
        """Mark quest as failed."""
        self.status = QuestStatus.FAILED

    def summary(self) -> str:
        """Return a one-line summary for display."""
        obj_text = "; ".join(
            f"{o.description} ({o.progress_text()})" for o in self.objectives
        )
        return f"[{self.status.value.upper()}] {self.title}: {obj_text}"


@dataclass
class WorldEvent:
    """
    A campaign world event that occurs during exploration.

    Attributes:
        event_type: Category of event
        title: Short title
        description: DM-narrated description
        options: Player choices (if any)
        outcomes: Outcome text per option index
        triggered: Whether event has fired
    """
    event_type: EventType
    title: str
    description: str
    options: List[str] = field(default_factory=list)
    outcomes: Dict[int, str] = field(default_factory=dict)
    triggered: bool = False

    def trigger(self) -> str:
        """Mark as triggered; return description."""
        self.triggered = True
        return self.description

    def resolve(self, choice: int) -> str:
        """Resolve with player choice; return outcome text."""
        return self.outcomes.get(choice, self.description)


@dataclass
class StoryArc:
    """
    A multi-quest story arc forming a campaign chapter.

    Attributes:
        id: Arc identifier
        title: Arc title
        premise: Opening story premise
        quests: Ordered list of quests
        world_events: Random events that can occur
        completed: Whether all quests done
        current_quest_idx: Index of active quest
    """
    id: str
    title: str
    premise: str
    quests: List[Quest] = field(default_factory=list)
    world_events: List[WorldEvent] = field(default_factory=list)
    completed: bool = False
    current_quest_idx: int = 0

    def current_quest(self) -> Optional[Quest]:
        """Return the current active quest, or None."""
        if self.current_quest_idx < len(self.quests):
            return self.quests[self.current_quest_idx]
        return None

    def advance(self) -> Optional[Quest]:
        """Move to the next quest. Returns new quest or None if arc done."""
        self.current_quest_idx += 1
        if self.current_quest_idx >= len(self.quests):
            self.completed = True
            return None
        next_q = self.quests[self.current_quest_idx]
        next_q.activate()
        return next_q

    def random_event(self, rng: random.Random) -> Optional[WorldEvent]:
        """Pick a random untriggered world event."""
        available = [e for e in self.world_events if not e.triggered]
        if not available:
            return None
        event = rng.choice(available)
        event.trigger()
        return event


# --- Campaign Templates ---

_KILL_QUESTS = [
    ("Goblin Problem", "Villagers are reporting goblin raids near the road.", "goblin", 3),
    ("Bone Pile", "The dead are walking in the old cemetery.", "skeleton", 5),
    ("Wolf Hunt", "A pack of dire wolves prowls the northern forest.", "wolf", 2),
]

_FETCH_QUESTS = [
    ("Lost Letter", "Bandits stole a merchant's important correspondence.", "letter", 1),
    ("Alchemist's Herbs", "The alchemist needs rare herbs from the forest.", "herb", 4),
    ("Sacred Relic", "A temple relic has gone missing — retrieve it.", "relic", 1),
]

_WORLD_EVENTS = [
    WorldEvent(
        event_type=EventType.AMBUSH,
        title="Roadside Ambush",
        description="Three bandits leap from the shadows!",
        options=["Fight", "Flee", "Negotiate"],
        outcomes={0: "Your courage sends them running.", 1: "You escape into the dark.", 2: "You pay 10 gold to pass."},
    ),
    WorldEvent(
        event_type=EventType.DISCOVERY,
        title="Hidden Passage",
        description="You find a concealed passage behind the wall.",
        options=["Enter", "Pass by"],
        outcomes={0: "Inside: an old chest with 25 gold!", 1: "You move on."},
    ),
    WorldEvent(
        event_type=EventType.WEATHER,
        title="Sudden Storm",
        description="A storm rolls in without warning.",
        options=["Take shelter", "Push through"],
        outcomes={0: "You find a nearby cave and wait it out.", 1: "You press on, soaked and weary. -5 HP."},
    ),
    WorldEvent(
        event_type=EventType.TRAP,
        title="Trapped!",
        description="A hidden pressure plate triggers beneath your foot!",
        options=["Jump clear", "Roll AGI"],
        outcomes={0: "You leap aside just in time!", 1: "The mechanism catches you. -8 HP."},
    ),
]


class CampaignGenerator:
    """
    Generates procedural story arcs and quest chains.

    Usage:
        gen = CampaignGenerator(seed=42)
        arc = gen.generate_arc(title="Karanlık Orman", num_quests=3)
        quest = arc.current_quest()
    """

    def __init__(self, seed: int = 0):
        self.seed = seed
        self.rng = random.Random(seed)
        self._arc_counter = 0

    def generate_arc(
        self,
        title: Optional[str] = None,
        num_quests: int = 3,
        location: str = "Unknown Lands",
    ) -> StoryArc:
        """
        Generate a story arc with mixed quest types.

        Args:
            title: Arc title (auto-generated if None)
            num_quests: Number of quests in arc (1-5)
            location: Primary location for this arc

        Returns:
            StoryArc with quests and world events
        """
        self._arc_counter += 1
        arc_id = f"arc_{self._arc_counter:03d}"

        if title is None:
            title = self.rng.choice([
                "Dark Forest", "Forgotten Tower", "Lost Treasure",
                "The Deceiver's Legacy", "Ruined Temple", "Threat from the North",
            ])

        premise = self.rng.choice([
            f"Dangerous events are unfolding in {location}. Someone must act.",
            f"An old prophecy is about to come true in {location}.",
            f"A stranger has arrived from {location} seeking help.",
        ])

        # Generate quests
        quests = []
        templates = self._build_quest_templates(location)
        selected = self.rng.sample(templates, min(num_quests, len(templates)))

        for i, template_fn in enumerate(selected):
            quest = template_fn(i + 1, location)
            if i == 0:
                quest.activate()
            quests.append(quest)

        # Add world events
        events = [WorldEvent(
            event_type=e.event_type,
            title=e.title,
            description=e.description,
            options=e.options.copy(),
            outcomes=e.outcomes.copy(),
        ) for e in self.rng.sample(_WORLD_EVENTS, min(2, len(_WORLD_EVENTS)))]

        return StoryArc(
            id=arc_id,
            title=title,
            premise=premise,
            quests=quests,
            world_events=events,
        )

    def _build_quest_templates(self, location: str):
        """Return list of quest factory functions."""
        templates = []

        # Kill quest
        kill_data = self.rng.choice(_KILL_QUESTS)
        def make_kill(idx, loc, d=kill_data):
            title, desc, target, count = d
            return Quest(
                id=f"q_{idx:03d}_kill",
                title=title,
                description=desc,
                quest_type=QuestType.KILL,
                giver="Village Elder",
                objectives=[QuestObjective(f"Kill {count} {target}s", target, count)],
                rewards={"gold": 50 * idx, "xp": 100 * idx},
                location=loc,
                difficulty=idx,
            )
        templates.append(make_kill)

        # Fetch quest
        fetch_data = self.rng.choice(_FETCH_QUESTS)
        def make_fetch(idx, loc, d=fetch_data):
            title, desc, item, count = d
            return Quest(
                id=f"q_{idx:03d}_fetch",
                title=title,
                description=desc,
                quest_type=QuestType.FETCH,
                giver="Merchant",
                objectives=[QuestObjective(f"Find {count} {item}(s)", item, count)],
                rewards={"gold": 40 * idx, "xp": 80 * idx},
                location=loc,
                difficulty=max(1, idx - 1),
            )
        templates.append(make_fetch)

        # Explore quest
        def make_explore(idx, loc):
            return Quest(
                id=f"q_{idx:03d}_explore",
                title="Exploration Mission",
                description=f"Scout the {loc} area and report back.",
                quest_type=QuestType.EXPLORE,
                giver="Guild Master",
                objectives=[QuestObjective(f"Map the {loc} area", loc, 1)],
                rewards={"gold": 30 * idx, "xp": 60 * idx},
                location=loc,
                difficulty=1,
            )
        templates.append(make_explore)

        # Dialogue quest
        def make_dialogue(idx, loc):
            return Quest(
                id=f"q_{idx:03d}_talk",
                title="The Elder's Secret",
                description="The village elder knows something. Find out what.",
                quest_type=QuestType.DIALOGUE,
                giver="Villagers",
                objectives=[QuestObjective("Speak with the Elder", "Elder", 1)],
                rewards={"gold": 20, "xp": 50 * idx},
                location=loc,
                difficulty=1,
            )
        templates.append(make_dialogue)

        return templates

    def generate_side_quest(self, location: str, difficulty: int = 1) -> Quest:
        """Generate a single side quest for a location."""
        templates = self._build_quest_templates(location)
        template_fn = self.rng.choice(templates)
        return template_fn(difficulty, location)


class CampaignManager:
    """
    Manages active campaigns, tracks quest progress.

    Usage:
        manager = CampaignManager()
        arc = manager.start_arc(gen.generate_arc())
        manager.complete_objective(arc.id, quest.id, "goblin", 1)
    """

    def __init__(self):
        self.arcs: Dict[str, StoryArc] = {}

    def start_arc(self, arc: StoryArc) -> StoryArc:
        """Register and start a story arc."""
        self.arcs[arc.id] = arc
        return arc

    def get_arc(self, arc_id: str) -> Optional[StoryArc]:
        """Retrieve a story arc by ID."""
        return self.arcs.get(arc_id)

    def complete_objective(
        self, arc_id: str, quest_id: str, target: str, amount: int = 1
    ) -> Optional[Dict]:
        """
        Advance an objective in a quest.
        Returns rewards dict if quest completes, else None.
        """
        arc = self.arcs.get(arc_id)
        if not arc:
            return None

        quest = next((q for q in arc.quests if q.id == quest_id), None)
        if not quest or quest.status != QuestStatus.ACTIVE:
            return None

        for obj in quest.objectives:
            if target.lower() in obj.target.lower() and not obj.completed:
                obj.progress(amount)

        if quest.is_complete():
            rewards = quest.complete()
            # Auto-advance arc
            arc.advance()
            return rewards

        return None

    def active_quests(self) -> List[Quest]:
        """Return all currently active quests across all arcs."""
        quests = []
        for arc in self.arcs.values():
            quests.extend(q for q in arc.quests if q.status == QuestStatus.ACTIVE)
        return quests

    def available_quests(self) -> List[Quest]:
        """Return all available (not yet started) quests."""
        quests = []
        for arc in self.arcs.values():
            quests.extend(q for q in arc.quests if q.status == QuestStatus.AVAILABLE)
        return quests
