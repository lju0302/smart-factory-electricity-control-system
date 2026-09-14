import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    duckdb_path: str
    duckdb_table: str
    eventhub_connection_str: str
    eventhub_name: str
    default_interval_seconds: float
    default_chunk_timestamps: int
    dry_run: bool


def get_settings() -> Settings:
    return Settings(
        duckdb_path=os.getenv("DUCKDB_PATH", "./db/smart_factory.duckdb"),
        duckdb_table=os.getenv("DUCKDB_TABLE", "power_clean"),
        eventhub_connection_str=os.getenv("EVENTHUB_CONNECTION_STR", ""),
        eventhub_name=os.getenv("EVENTHUB_NAME", ""),
        default_interval_seconds=float(os.getenv("DEFAULT_INTERVAL_SECONDS", "0.5")),
        default_chunk_timestamps=int(os.getenv("DEFAULT_CHUNK_TIMESTAMPS", "20")),
        dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
    )