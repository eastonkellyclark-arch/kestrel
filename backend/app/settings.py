"""Centralised configuration. Every setting comes from environment variables.

Import `settings` from this module — never read os.environ elsewhere.
"""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "KESTREL_", "env_file": ".env"}

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Database — resolved to absolute at startup so CWD changes can't move it
    data_dir: Path = Path("./data")

    def model_post_init(self, __context: object) -> None:
        # Resolve relative data_dir to absolute against CWD at startup time
        object.__setattr__(self, "data_dir", self.data_dir.resolve())

    # Adzuna (Phase 8)
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    adzuna_daily_budget: int = 33

    # USAJobs (Phase 8)
    usajobs_api_key: str = ""
    usajobs_email: str = ""

    # Gmail (Phase 10)
    gmail_credentials_json: str = ""
    gmail_token_json: str = ""

    # SAM.gov (Phase 11)
    sam_api_key: str = ""

    # Location
    home_lat: float = 44.640
    home_lon: float = -93.144
    onsite_radius_km: float = 80.0

    @property
    def database_path(self) -> Path:
        return self.data_dir / "kestrel.db"


settings = Settings()
