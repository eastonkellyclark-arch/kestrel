"""Standalone entrypoint: python -m backend.export_public

Exports the public dataset as split JSON for the showroom build.
Output: {data_dir}/export/index.json + {data_dir}/export/listings/{id}.json
"""

from app.database import init_db
from app.export import export_public
from app.settings import settings

if __name__ == "__main__":
    init_db()
    output_dir = settings.data_dir / "export"
    count = export_public(output_dir)
    print(f"Exported {count} listings to {output_dir}")
