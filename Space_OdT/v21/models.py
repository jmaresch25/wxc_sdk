from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    LOCATION = 'location'
    USER = 'user'
    WORKSPACE = 'workspace'


class Stage(str, Enum):
    LOCATION_CREATE_AND_ACTIVATE = 'location_create_and_activate'


@dataclass(frozen=True)
class LocationInput:
    row_number: int
    location_name: str
    location_id: str | None
    org_id: str | None
    route_group_id: str | None
    main_number: str | None
    default_outgoing_profile: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class UserInput:
    row_number: int
    user_email: str
    user_id: str | None
    location_name: str | None
    location_id: str | None
    extension: str | None
    legacy_secondary_number: str | None
    legacy_forward_target: str | None
    outgoing_profile: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class WorkspaceInput:
    row_number: int
    workspace_name: str
    workspace_id: str | None
    location_name: str | None
    location_id: str | None
    extension: str | None
    legacy_secondary_number: str | None
    legacy_forward_target: str | None
    outgoing_profile: str | None
    payload: dict[str, Any]


@dataclass
class PlannedAction:
    entity_type: EntityType
    entity_key: str
    stage: Stage
    mode: str
    details: str


@dataclass
class RunSummary:
    run_id: str
    mode: str
    completed_count: int
    failed_count: int
    planned_count: int
    outputs: dict[str, str] = field(default_factory=dict)
