"""Load the company registry from config/registry.json.

This file is committed — both local dev and CI read the same registry.
The desk UI writes to it so additions persist across environments.
"""

import json
from pathlib import Path

from .database import init_db
from .models import ATSPlatform, RegistryEntry
from .repository import upsert_registry

_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "registry.json"


def load_registry() -> list[dict]:
    """Read registry.json."""
    if not _REGISTRY_PATH.exists():
        return []
    with open(_REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_registry(entries: list[dict]) -> None:
    """Write registry.json."""
    with open(_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")


def seed() -> None:
    """Sync registry.json into the SQLite registry table."""
    init_db()
    entries = load_registry()
    for entry in entries:
        upsert_registry(RegistryEntry(
            id=None,
            company=entry["company"],
            platform=ATSPlatform(entry["platform"]),
            board_slug=entry["board_slug"],
            active=entry.get("active", True),
        ))
    print(f"Loaded {len(entries)} companies from registry.json")


if __name__ == "__main__":
    seed()
