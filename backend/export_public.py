"""Standalone entrypoint: python -m backend.export_public

Exports the public dataset to JSON for the showroom build.
"""

from pathlib import Path

from app.database import init_db
from app.export import export_public
from app.settings import settings

if __name__ == "__main__":
    init_db()
    output = settings.data_dir / "public_export.json"
    count = export_public(output)
    print(f"Exported {count} listings to {output}")
