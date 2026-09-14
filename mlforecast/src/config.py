# src/config.py

from dotenv import load_dotenv
import os
from dataclasses import dataclass

load_dotenv()

@dataclass
class Settings:
    sql_server: str
    sql_database: str
    sql_username: str
    sql_password: str
    sql_driver: str

    input_table: str
    output_table: str

    model_dir_nhits: str
    model_dir_tft: str

    forecast_horizon: int


def get_settings() -> Settings:
    return Settings(
        sql_server=os.environ["SQL_SERVER"],
        sql_database=os.environ["SQL_DATABASE"],
        sql_username=os.environ["SQL_USERNAME"],
        sql_password=os.environ["SQL_PASSWORD"],
        sql_driver=os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server"),

        input_table=os.getenv("INPUT_TABLE", "dbo.poweroutput_15m"),
        output_table=os.getenv("OUTPUT_TABLE", "dbo.power_forecast_result"),

        model_dir_nhits=os.getenv("MODEL_DIR_NHITS", "./models/NHITS"),
        model_dir_tft=os.getenv("MODEL_DIR_TFT", "./models/TFT"),

        forecast_horizon=int(os.getenv("FORECAST_HORIZON", "96")),
    )

