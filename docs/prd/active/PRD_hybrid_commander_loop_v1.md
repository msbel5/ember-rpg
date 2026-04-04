# PRD: Hybrid Commander Loop V1
**Project:** Ember RPG
**Phase:** 4
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines how macro colony/world play and local commander-avatar play coexist under a single deterministic runtime. The player manages pressure at the node/site level (colony-sim mode) while also walking, talking, fighting, and inspecting the active site in person (CRPG mode). This is the bridge between RimWorld-style oversight and Planescape-style avatar exploration.

## 2. Scope

- In scope: macro vs local loop boundaries, travel state machine, active-site hydration, commander-avatar continuity, deterministic tick ownership, military squad basics, pathfinding authority
- Out of scope: LLM narration, final map polish, final tutorial onboarding, full tactical combat system (see `PRD_combat_resolution_v1`)

## 3. Reference Mechanism Coverage

| DF Mechanism | Coverage | Notes |
|-------------|----------|-------|
| M15 Pathfinding | Travel graph + local authority | A* on search map deferred; travel graph is node-based |
| M18 Military | Squad baseline | Squad creation, posture, orders; formation/engagement deferred |
| M01 Combat | Commander participates | Avatar can enter combat in active site |
| M20 Diplomacy | Faction encounters | Travel may trigger faction events |

## 4. Data Structures

```python
@dataclass
class TravelState:
    """State machine for inter-region travel."""
    status: str  # "idle", "preparing", "traveling", "arriving", "arrived"
    origin_region_id: str = ""
    destination_region_id: str = ""
    travel_hours_remaining: int = 0
    travel_hours_total: int = 0
    encounter_roll: float = 0.0  # random encounter probability consumed
    encounter_triggered: bool = False

@dataclass
class PathAuthorityState:
    """Tracks which region/site is currently active for local pathfinding."""
    active_region_id: str = ""
    active_site_id: str = ""
    local_map_loaded: bool = False
    spawn_point: list[int] = field(default_factory=lambda: [10, 7])

@dataclass
class LocalMapState:
    """Terrain info for the currently hydrated local map."""
    region_id: str = ""
    width: int = 80
    height: int = 60
    biome_id: str = ""
    spawn_point: list[int] = field(default_factory=lambda: [10, 7])
    terrain_tags: list[str] = field(default_factory=list)

@dataclass
class SquadMemberRecord:
    actor_id: str
    role: str = "soldier"  # "leader", "soldier", "medic", "scout"
    duty: str = "garrison"  # "garrison", "patrol", "escort", "raid"
    equipment_policy: str = "default"

@dataclass
class SquadRecord:
    squad_id: str
    name: str
    posture: str = "defensive"  # "defensive", "aggressive", "patrol", "escort"
    members: list[SquadMemberRecord] = field(default_factory=list)
    orders: list[str] = field(default_factory=list)  # ["guard_gate", "patrol_market", "escort_caravan"]
    equipment_policy: str = "melee_heavy"

@dataclass
class MilitaryState:
    squads: list[SquadRecord] = field(default_factory=list)
    defense_posture: str = "normal"  # "normal", "alert", "fortified"
    alert_level: int = 0  # 0=peace, 1=concern, 2=threat, 3=siege
```

## 5. Functional Requirements (FR)

### Macro Loop
FR-01: The game must expose a macro loop where the player inspects world graph pressure, factions, sites, and travel routes.
FR-02: Macro state is read from `WorldState` — regions, factions, travel edges, economy, alerts.
FR-03: The player can initiate travel to a connected region via explicit travel command (not string-matched shortcut).

### Travel State Machine
FR-04: Travel follows a state machine: idle → preparing → traveling → arriving → arrived.
FR-05: During "traveling" state, travel_hours_remaining decrements each world tick. Random encounter check occurs once per travel (probability from TravelEdge.danger_level).
FR-06: If encounter triggered, travel pauses and combat/event resolves before arrival.
FR-07: On arrival, active_region_id changes, local map rehydrates for destination only.

### Local Loop
FR-08: The game exposes a local loop where the commander-avatar operates inside the currently active site.
FR-09: Local actions (move, talk, fight, examine, craft) consume AP and advance the world tick.
FR-10: Colony pressure updates on the same tick as local actions — no separate "colony turn" vs "avatar turn."

### Military
FR-11: Military state tracks squads with members, posture, and standing orders.
FR-12: Defense posture (normal/alert/fortified) affects trap arming (see `PRD_systems_closure_v1`), NPC schedules, and patrol routes.
FR-13: Squad orders are standing instructions, not real-time pathfinding commands. Execution is abstracted: guards at their posts reduce threat pressure; patrols reduce bandit encounter rate.

### Authority
FR-14: AI narration and NPC conversation are optional adapters, not authorities. Core gameplay is fully playable without them.
FR-15: `WorldState` is the single macro authority. `GameSession` is a projection, not an independent simulation.

## 6. Public API

```python
def initiate_travel(world_state: WorldState, origin_id: str, destination_id: str, seed: int) -> TravelState:
    """Begin travel between regions. Returns TravelState in 'preparing' status.
    Precondition: TravelEdge exists between origin and destination.
    Raises: ValueError if no edge connects origin to destination.
    """

def tick_travel(travel: TravelState, seed: int) -> TravelState:
    """Advance travel by one world tick (1 hour). Decrements remaining hours.
    Checks random encounter on first tick. Returns updated TravelState.
    """

def complete_travel(travel: TravelState, world_state: WorldState) -> PathAuthorityState:
    """Finalize arrival. Updates active_region_id. Returns new PathAuthorityState.
    Precondition: travel.status == 'arrived'.
    """

def hydrate_local_map(world_state: WorldState, region_id: str) -> LocalMapState:
    """Load local map for the given region. Only one region hydrated at a time."""

def military_state_from_settlement(settlement_state: dict) -> MilitaryState:
    """Build military state from settlement residents and defense posture."""

def apply_squad_orders(military: MilitaryState, colony_pressure: ColonyPressureState) -> ColonyPressureState:
    """Apply standing military orders to colony pressure. Guards reduce safety pressure; patrols reduce unrest."""
```

## 7. Acceptance Criteria (AC)

AC-01 [FR-01,FR-02]: Given a campaign snapshot, when macro state is queried, then world graph, faction pressure, and travel options are explicit typed records.
AC-02 [FR-03,FR-04]: Given a travel command to a connected region, when initiated, TravelState enters "preparing" with correct origin/destination and travel hours from TravelEdge.
AC-03 [FR-05]: Given a TravelState in "traveling" status, each tick_travel call decrements travel_hours_remaining by 1. When remaining reaches 0, status transitions to "arrived."
AC-04 [FR-06]: Given a TravelEdge with danger_level=2, when traveling, encounter check uses danger_level-proportional probability. If triggered, travel.encounter_triggered=True.
AC-05 [FR-07]: Given travel completed, when complete_travel called, active_region_id updates to destination and PathAuthorityState reflects new region.
AC-06 [FR-08,FR-09]: Given commander-avatar in active site, local actions consume AP and advance world tick. Colony pressure recalculates on same tick.
AC-07 [FR-10]: Given a local action that advances time by 1 hour, colony pressure food/safety/morale update on same tick (not deferred to separate pass).
AC-08 [FR-11,FR-12]: Given settlement with fortified posture, military_state_from_settlement creates squad with guard/patrol orders and alert_level reflects defense_posture.
AC-09 [FR-13]: Given squad with "guard_gate" order, apply_squad_orders reduces colony safety pressure by guard_count × 5.
AC-10 [FR-14]: Given no AI narrator or NPC conversation adapter, core travel/combat/colony loop runs without error.

## 8. Performance Requirements

- Travel initiation: < 50ms
- Travel tick: < 10ms
- Local map hydration: < 500ms
- Military state build: < 10ms

## 9. Error Handling

- Travel to unconnected region: raise ValueError with clear message
- Travel tick on non-traveling state: return unchanged state, log warning
- Hydrate local map for unknown region: return default empty LocalMapState, log warning
- Military from empty settlement: return MilitaryState with empty squads

## 10. Integration Points

- `engine/kernel/world_state.py` — WorldState is the macro authority
- `engine/kernel/actor.py` — commander-avatar is an ActorRecord in the active region
- `engine/kernel/colony.py` — colony pressure updates on shared tick
- `engine/kernel/combat.py` — combat resolves in active site during travel encounters or local play
- `engine/kernel/systems.py` — defense posture affects trap arming
- `engine/api/campaign/runtime.py` — travel commands route through campaign runtime
- `godot-client` — map/session surfaces consume PathAuthorityState and LocalMapState

## 11. Test Coverage Target

- Travel state machine: all transitions (idle→preparing→traveling→arriving→arrived)
- Random encounter triggering with deterministic seed
- Shared tick progression (local action + colony pressure on same tick)
- Military order effects on colony pressure
- Local map hydration correctness
- 85% line coverage

## Changelog

- 2026-04-01: Expanded from 55-line stub to full PRD with TravelState machine, military structures, 10 ACs, API signatures, error handling. Added data structure definitions from kernel/hybrid.py.
