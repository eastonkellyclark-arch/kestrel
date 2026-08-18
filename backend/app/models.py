"""Domain types used across the application. No ORM — just typed containers."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ATSPlatform(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    RECRUITEE = "recruitee"


class FetchOutcome(str, Enum):
    SUCCESS = "success"
    EMPTY_BOARD = "empty_board"
    SLUG_NOT_FOUND = "slug_not_found"
    BOARD_DISABLED = "board_disabled"
    NETWORK_ERROR = "network_error"


@dataclass
class RegistryEntry:
    id: int | None
    company: str
    platform: ATSPlatform
    board_slug: str
    active: bool = True
    added_date: str = field(default_factory=lambda: datetime.utcnow().date().isoformat())


@dataclass
class FetchResult:
    company: str
    platform: ATSPlatform
    board_slug: str
    outcome: FetchOutcome
    job_count: int = 0
    error_detail: str = ""
