from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.kernel.common import serialize_value
from engine.worldgen.models import RegionSnapshot, WorldBlueprint


@dataclass
class PathAuthorityState:
    active_region_id: str
    active_site_id: str
    local_map_id: str
    hydrated_from_region: bool
    travel_edge_count: int
    reindex_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class LocalMapState:
    region_id: str
    site_id: str
    width: int
    height: int
    spawn_point: list[int]
    terrain_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class SquadMemberRecord:
    actor_id: str
    label: str
    duty: str
    drafted: bool

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class SquadRecord:
    squad_id: str
    label: str
    posture: str
    members: list[SquadMemberRecord] = field(default_factory=list)
    orders: list[str] = field(default_factory=list)
    equipment_policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


@dataclass
class MilitaryState:
    squads: list[SquadRecord] = field(default_factory=list)
    defense_posture: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)


def path_authority_from_world(world: WorldBlueprint, region_snapshot: RegionSnapshot) -> PathAuthorityState:
    active_region_id = str(world.simulation_snapshot.active_region_id if world.simulation_snapshot else region_snapshot.region_id)
    active_site_id = str(
        next(
            (
                node["id"]
                for node in world.settlement_nodes
                if str(node.get("region_id")) == region_snapshot.region_id
            ),
            region_snapshot.region_id,
        )
    )
    return PathAuthorityState(
        active_region_id=active_region_id,
        active_site_id=active_site_id,
        local_map_id=f"region::{region_snapshot.region_id}",
        hydrated_from_region=True,
        travel_edge_count=sum(
            1
            for edge in world.travel_edges
            if edge.get("from_region_id") == region_snapshot.region_id or edge.get("to_region_id") == region_snapshot.region_id
        ),
        reindex_required=False,
    )


def local_map_state_from_region(region_snapshot: RegionSnapshot) -> LocalMapState:
    terrain_tags = sorted(
        {
            str(tile.get("terrain", "unknown"))
            for row in region_snapshot.typed_tiles
            for tile in row
        }
    )
    active_site_id = str(
        region_snapshot.metadata.get("settlement_id", region_snapshot.region_id)
        or region_snapshot.region_id
    )
    return LocalMapState(
        region_id=region_snapshot.region_id,
        site_id=active_site_id,
        width=region_snapshot.width,
        height=region_snapshot.height,
        spawn_point=[int(region_snapshot.layout.center_feature["x"]), int(region_snapshot.layout.center_feature["y"])],
        terrain_tags=terrain_tags[:12],
    )


def military_state_from_settlement(settlement_state: dict[str, Any]) -> MilitaryState:
    defense_posture = str(settlement_state.get("defense_posture", "normal"))
    members: list[SquadMemberRecord] = []
    for resident in settlement_state.get("residents", []):
        drafted = bool(resident.get("drafted"))
        if drafted or str(resident.get("role")) in {"commander", "guard", "warden"}:
            members.append(
                SquadMemberRecord(
                    actor_id=str(resident.get("id", "")),
                    label=str(resident.get("name", resident.get("id", "Resident"))),
                    duty=str(resident.get("assignment", "reserve")),
                    drafted=drafted,
                )
            )
    if not members and settlement_state.get("residents"):
        commander = settlement_state["residents"][0]
        members.append(
            SquadMemberRecord(
                actor_id=str(commander.get("id", "")),
                label=str(commander.get("name", "Commander")),
                duty="command",
                drafted=False,
            )
        )

    orders = ["guard_gate", "patrol_market"] if defense_posture == "fortified" else ["reserve", "escort"]
    squad = SquadRecord(
        squad_id="settlement_watch",
        label="Settlement Watch",
        posture=defense_posture,
        members=members,
        orders=orders,
        equipment_policy={
            "weapon": "best_available",
            "armor": "best_available" if defense_posture == "fortified" else "standard_issue",
        },
    )
    return MilitaryState(squads=[squad], defense_posture=defense_posture)
