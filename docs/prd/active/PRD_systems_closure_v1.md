# PRD: Systems Closure (Sprint 5 Baseline)
**Project:** Ember RPG
**Phase:** 5
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Provides deterministic baseline implementations for the six deferred subsystems: syndromes/disease (DF M06), power networks (DF M07), traps (DF M08), fluid simulation (DF M09), temperature effects (DF M10), and strange moods/artifacts (DF M13). Each subsystem must have typed data structures, a tick-driven update pipeline, and at least one integration test. These are SIMULATION systems, not just metadata — they must produce observable consequences in the world tick.

## 2. Scope

**In scope:**
- Syndrome transmission and progression mechanics
- Power network distribution with source/consumer/transmitter topology
- Trap trigger, damage, and rearm pipeline
- Fluid flow basics: spreading, drowning, magma damage
- Temperature effects on actors and items: freezing, burning, ignition
- Strange mood full lifecycle: trigger → material demand → artifact creation → skill boost OR insanity

**Out of scope:**
- Full DF-fidelity voxel fluid dynamics
- Multi-z-level power transmission
- Trap construction UI
- Weather-driven temperature (handled by world tick, not this module)
- Visual/Godot rendering of these systems

## 2.1 Runtime Authority Closure

Systems closure is only complete when its consequences are observed in live
campaign state, not merely in isolated kernel tests. Active runtime must apply
the systems phase after effects/syndromes and before persistence projection:

1. power network recompute
2. fluid tick and drowning/magma checks
3. temperature tick and resulting wounds/conditions
4. trap trigger resolution
5. strange mood lifecycle advance
6. syndrome registry refresh

Authoritative runtime surfaces:
- `frp-backend/engine/api/campaign/live_kernel.py`
- `frp-backend/engine/api/campaign/runtime.py`
- `frp-backend/engine/api/campaign/persistence.py`

These results must alter canonical `actors`, `systems`, `world_state`, and
settlement projections that are sent to Godot and saved back through
`kernel_systems`.

## 3. Functional Requirements (FR)

### Syndromes (DF M06)
FR-01: `SyndromeDef` specifies delivery method (contact, inhaled, injected, ingested), resistance DC, and a list of timed `SyndromeEffect` entries.
FR-02: Applying a syndrome to an actor checks resistance: d20 + disease_resistance + toughness/2 vs syndrome.resistance_dc. On failure, syndrome is applied.
FR-03: Each `SyndromeEffect` has start_tick, end_tick (or -1 for permanent), and severity. Active effects modify actor state each tick.
FR-04: Syndrome effect types include: CE_PAIN, CE_BLEEDING, CE_PARALYSIS, CE_NAUSEA, CE_FEVER, CE_NUMBNESS, CE_UNCONSCIOUSNESS, CE_NECROSIS, CE_PERSONALITY_CHANGE, CE_SPEED_CHANGE, CE_STAT_CHANGE.
FR-05: Contagion: actors with active contagious syndrome in the same region tile can transmit via SYN_CONTACT to adjacent actors (probability per tick).

### Power Networks (DF M07)
FR-06: `PowerNetworkState` tracks connected components. Sources produce power, consumers require power, transmitters relay with optional loss.
FR-07: Network activation rule: if total_available >= total_required, ALL consumers active. If shortfall, NOTHING works (all-or-nothing, matching DF).
FR-08: Lever-linked `GearAssembly` nodes can disconnect sub-networks (on/off switch), reducing demand.
FR-09: Power sources: water_wheel (+20), windmill (+40 above ground, 0 underground), manual_crank (+5). Consumers: forge (-10), mill (-10), pump (-10), roller (-10). Transmitters: gear_assembly (0 loss), axle (-1 per tile length).

### Traps (DF M08)
FR-10: `TrapState` tracks trap_type, armed status, trigger type, and loaded components (weapons for weapon_trap, mechanism for cage_trap).
FR-11: Trap trigger pipeline: hostile unit enters tile → trigger check (trap_avoid creatures immune) → if triggered: weapon_trap fires all loaded weapons as strikes; cage_trap captures unit; stone_fall_trap deals blunt damage proportional to stone weight.
FR-12: Weapon traps are reusable. Cage traps and stone-fall traps are single-use (armed=false after trigger).
FR-13: Upright spike traps are lever-linked: on trigger signal, spikes extend and attack all units in tile.

### Fluid Simulation (DF M09)
FR-14: `FluidCell` tracks fluid_type (water or magma) and level (0-7). Fluid spreads to adjacent cells with lower level each tick.
FR-15: Drowning: actor in level 7 water → suffocation timer starts (10 ticks). If not rescued, death.
FR-16: Magma damage: actor in any level magma → severe burn wound + ignition condition each tick.
FR-17: Water + magma on same tile → obsidian (solid wall created, both fluids consumed).
FR-18: Muddy floor: water receding from soil tile → muddy flag → enables farming on that tile.

### Temperature (DF M10)
FR-19: `TemperatureState` tracks ambient temperature per region. Heat sources (magma, forge, fire) radiate heat to surrounding tiles.
FR-20: Cold damage: actor.temperature below cold_threshold for sustained ticks → frostbite wound (type=cold).
FR-21: Heat damage: actor.temperature above heat_threshold → burn wound (type=fire). Organic items at ignite_point → burning condition.
FR-22: Water freezing: tile temperature below freeze_point → water becomes ice (impassable). Above freeze_point → ice melts back to water.

### Strange Moods (DF M13)
FR-23: Trigger conditions: eligible actor (has moodable skill, hasn't had mood before) + colony morale < 70 or unrest > 50.
FR-24: Mood types: fey_crafter (happy → artifact, skill boost), secretive (quiet → artifact, no skill boost), possessed (entity → artifact, no XP), macabre (dark → requires bones), fell (murderous → kills nearest, uses corpse).
FR-25: Material demand phase: mood actor claims workshop → demands 1-8 materials based on highest skill + preferences. If materials unavailable after timeout (500 ticks), mood fails.
FR-26: Artifact creation: on success, creates artifact-quality item (quality=6, value ×120, combat ×3). Creator's relevant skill jumps to legendary (rating 20). Large positive morale effect.
FR-27: Mood failure: timeout without workshop → insane. Timeout without materials → insane or melancholy or berserk. Insane = random destructive behavior. Melancholy = withdraw, refuse food, eventual death.

## 4. Data Structures

```python
# --- Syndromes ---
@dataclass
class SyndromeEffect:
    effect_id: str
    effect_type: str  # CE_PAIN, CE_BLEEDING, CE_PARALYSIS, etc.
    severity: int  # 0-100
    target: str  # "actor" or "body_part:{part_id}"
    start_tick: int = 0
    end_tick: int = -1  # -1 = permanent
    tick_counter: int = 0

@dataclass
class SyndromeDef:
    syndrome_id: str
    name: str
    delivery: str  # "contact", "inhaled", "injected", "ingested"
    resistance_dc: int = 10
    contagious: bool = False
    contagion_probability: float = 0.05  # per tick per adjacent actor
    effects: list[SyndromeEffect] = field(default_factory=list)

# --- Power ---
@dataclass
class PowerNodeState:
    node_id: str
    kind: str  # "water_wheel", "windmill", "forge", "gear_assembly", "axle"
    role: str  # "source", "consumer", "transmitter"
    power_delta: int  # positive=source, negative=consumer, 0=transmitter
    connected_to: list[str] = field(default_factory=list)
    disengaged: bool = False

@dataclass
class PowerNetworkState:
    nodes: list[PowerNodeState] = field(default_factory=list)
    total_available: int = 0
    total_required: int = 0
    active: bool = False

# --- Traps ---
@dataclass
class TrapComponent:
    component_id: str
    component_type: str  # "mechanism", "weapon", "cage", "stone"
    material_id: str = "iron"
    quality: int = 0

@dataclass
class TrapState:
    trap_id: str
    trap_type: str  # "weapon_trap", "cage_trap", "stone_fall", "upright_spike"
    armed: bool = True
    trigger: str  # "pressure_plate", "lever"
    components: list[TrapComponent] = field(default_factory=list)
    reusable: bool = False
    linked_lever_id: str | None = None

# --- Fluids ---
@dataclass
class FluidCell:
    x: int
    y: int
    fluid_type: str  # "water", "magma"
    level: int  # 0-7

@dataclass
class FluidState:
    cells: list[FluidCell] = field(default_factory=list)
    fluid_counts: dict[str, int] = field(default_factory=dict)
    pressure_enabled: bool = False
    muddy_floor_risk: bool = False

# --- Temperature ---
@dataclass
class TemperatureState:
    ambient_band: str  # "cold", "temperate", "hot"
    ambient_value: int = 10015  # DF units, ~65°F
    hazardous: bool = False
    heat_sources: list[dict] = field(default_factory=list)
    cold_threshold: int = 10000  # freezing point
    heat_threshold: int = 10500  # burn threshold
    tags: list[str] = field(default_factory=list)

# --- Strange Moods ---
@dataclass
class MaterialDemand:
    material_tag: str  # "metal_bar", "gem", "bone", "cloth", "leather", "wood", "stone"
    satisfied: bool = False

@dataclass
class StrangeMoodIncident:
    incident_id: str
    state: str  # "triggered", "claiming_workshop", "demanding_materials", "working", "completed", "failed"
    mood_type: str  # "fey_crafter", "secretive", "possessed", "macabre", "fell"
    trigger_reason: str
    actor_id: str = ""
    claimed_worksite_id: str = ""
    material_demands: list[MaterialDemand] = field(default_factory=list)
    timeout_ticks: int = 500
    elapsed_ticks: int = 0
    artifact_item_id: str | None = None
    candidate_actor_ids: list[str] = field(default_factory=list)
```

## 5. Public API

```python
# Syndromes
def apply_syndrome(actor: ActorRecord, syndrome: SyndromeDef, seed: int) -> bool:
    """Apply syndrome to actor. Returns True if resistance check failed (syndrome applied).
    Precondition: actor and syndrome are valid.
    Postcondition: actor.conditions updated with syndrome effects if resistance failed.
    """

def tick_syndromes(actor: ActorRecord) -> list[str]:
    """Advance all active syndrome effects by one tick. Returns list of event descriptions.
    Expired effects are removed. Active effects modify actor state.
    """

def spread_contagion(actors: list[ActorRecord], region_tiles: dict) -> list[tuple[str, str]]:
    """Check contagion spread between adjacent actors. Returns list of (source_id, target_id) new infections."""

# Power
def compute_power_network(settlement_state: dict) -> PowerNetworkState:
    """Build power network from settlement workstations and connections.
    Includes connected component analysis and activation check.
    """

def toggle_gear(network: PowerNetworkState, gear_id: str) -> PowerNetworkState:
    """Disengage or reengage a gear assembly node. Recalculates network activation."""

# Traps
def check_trap_triggers(traps: list[TrapState], unit_positions: dict[str, tuple]) -> list[dict]:
    """Check if any armed traps are triggered by unit positions. Returns list of trigger events.
    Each event: {trap_id, target_actor_id, damage_type, damage_amount, captured}
    """

def resolve_trap_damage(trap: TrapState, target: ActorRecord, seed: int) -> list[WoundRecord]:
    """Resolve damage from triggered trap. Returns wounds applied to target."""

# Fluids
def tick_fluids(fluid_state: FluidState, terrain: list[list[dict]]) -> FluidState:
    """Advance fluid simulation by one tick. Spreads fluid, checks obsidian creation."""

def check_drowning(actor: ActorRecord, fluid_state: FluidState) -> bool:
    """Returns True if actor is in level 7 water (drowning risk)."""

def check_magma_damage(actor: ActorRecord, fluid_state: FluidState) -> WoundRecord | None:
    """Returns burn wound if actor is in magma tile."""

# Temperature
def tick_temperature(temp_state: TemperatureState, actors: list[ActorRecord]) -> list[dict]:
    """Check temperature effects on actors. Returns list of cold/heat damage events."""

# Strange Moods
def tick_strange_mood(incident: StrangeMoodIncident, settlement: dict, actors: list[ActorRecord], seed: int) -> StrangeMoodIncident:
    """Advance strange mood state machine by one tick. Returns updated incident.
    States: triggered → claiming_workshop → demanding_materials → working → completed/failed
    """

def create_artifact(incident: StrangeMoodIncident, actor: ActorRecord, seed: int) -> ItemStack:
    """Create artifact-quality item from successful mood. Updates actor skill to legendary."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-01,FR-02]: Given a syndrome with resistance_dc=15 and actor with disease_resistance=3 and toughness=12, when applied with seed producing d20=10, then resistance check = 10+3+6 = 19 >= 15 → syndrome resisted (not applied).
AC-02 [FR-03]: Given an actor with active syndrome effect CE_PAIN(severity=50, start=0, end=100), when tick_syndromes called at tick 50, then actor.pain increased by severity-proportional amount. When called at tick 101, effect removed.
AC-03 [FR-04]: Given syndrome with CE_BLEEDING effect, ticking produces bleeding damage proportional to severity each tick.
AC-04 [FR-05]: Given two actors in same tile, one with contagious syndrome, contagion check with probability 0.05 per tick transmits to adjacent actor at expected rate.
AC-05 [FR-06,FR-07]: Given power network with water_wheel(+20) and forge(-10)+mill(-10), total_available=20 >= total_required=20 → network active. Remove water_wheel → shortfall → ALL consumers inactive.
AC-06 [FR-08]: Given gear_assembly linked to lever, toggling gear disconnects sub-network → reduces required power → remaining network may activate.
AC-07 [FR-10,FR-11]: Given armed weapon_trap with 3 loaded weapons, hostile unit enters tile → trap triggers → 3 strike resolutions against target → trap remains armed (reusable).
AC-08 [FR-11]: Given armed cage_trap, hostile unit enters tile → unit captured → trap disarmed (single-use). Trap-avoid creature does NOT trigger cage trap.
AC-09 [FR-14]: Given fluid cells with water level 7 at (5,5) and level 0 at (5,6), tick_fluids spreads water: (5,5) decreases, (5,6) increases.
AC-10 [FR-15]: Given actor in level 7 water for 10+ ticks, check_drowning returns True → suffocation death.
AC-11 [FR-16,FR-17]: Given water cell and magma cell on same tile, tick_fluids creates obsidian (both consumed).
AC-12 [FR-19,FR-20]: Given actor in cold region (ambient < cold_threshold) for sustained ticks, tick_temperature returns frostbite wound event.
AC-13 [FR-21]: Given organic item at temperature above ignite_point, tick_temperature returns burning condition event.
AC-14 [FR-22]: Given water tile at temperature below freeze_point, tick produces ice wall. Above freeze_point, ice melts to water.
AC-15 [FR-23,FR-24]: Given settlement with morale < 70 and eligible actor, strange mood triggers with mood_type based on personality.
AC-16 [FR-25]: Given mood actor with material demands, all demands satisfied → state transitions to "working". Timeout without materials → state "failed".
AC-17 [FR-26]: Given successful mood completion, artifact item created with quality=6, actor skill set to 20 (legendary).
AC-18 [FR-27]: Given mood failure (timeout), actor condition set to "insane" or "melancholy" depending on mood_type.

## 7. Performance Requirements

- Syndrome tick for 100 actors with 5 active effects each: < 10ms
- Power network computation for 50 nodes: < 5ms
- Fluid tick for 100 cells: < 10ms
- Temperature check for 50 actors: < 5ms
- Strange mood tick: < 1ms

## 8. Error Handling

- Syndrome with unknown effect_type: log warning, skip effect, do not crash
- Power network with circular connections: detect cycle, treat as single component
- Trap trigger on dead/captured actor: skip, do not apply damage
- Fluid cell with invalid level (>7 or <0): clamp to valid range
- Strange mood on actor with no moodable skill: skip, return None

## 9. Integration Points

- `engine/kernel/actor.py` — syndromes modify actor conditions; temperature/fluid create wounds
- `engine/kernel/combat.py` — trap damage uses resolve_strike pipeline
- `engine/kernel/colony.py` — strange mood affects colony morale; power network enables workshops
- `engine/kernel/effects.py` (new) — syndrome effects route through unified effect system
- `engine/worldgen/world_tick.py` — all systems tick during world update
- `engine/api/campaign/persistence.py` — systems state exposed in campaign payloads

## 10. Test Coverage Target

- 90% line coverage for all public functions
- Every AC maps to at least one pytest test
- Edge cases: empty actor list, empty network, no fluid cells, mood with no candidates
- Deterministic: same seed produces same results

## Reference Mechanism Coverage

| DF Mechanism | Coverage | Notes |
|-------------|----------|-------|
| M06 Syndrome/Poison | Full baseline | Transmission, progression, 11 effect types |
| M07 Machine/Power | Full baseline | Source/consumer/transmitter, all-or-nothing activation |
| M08 Traps | Full baseline | Weapon/cage/stone/spike, trigger pipeline, rearm rules |
| M09 Fluid Simulation | Simplified | 2D spreading, drowning, magma damage, obsidian |
| M10 Temperature | Simplified | Ambient bands, freeze/burn thresholds, heat sources |
| M13 Strange Mood | Full lifecycle | Trigger → demand → create/fail, artifact quality, insanity |
