# src/db.py

import urllib.parse
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config import Settings


def create_sql_engine(settings: Settings) -> Engine:
    connection_string = (
        f"DRIVER={{{settings.sql_driver}}};"
        f"SERVER={settings.sql_server};"
        f"DATABASE={settings.sql_database};"
        f"UID={settings.sql_username};"
        f"PWD={settings.sql_password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    params = urllib.parse.quote_plus(connection_string)

    return create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}",
        pool_pre_ping=True,
        fast_executemany=True,
    )


def get_base_time(engine: Engine, input_table: str) -> pd.Timestamp:
    query = text(f"""
        SELECT DATEADD(HOUR, DATEDIFF(HOUR, 0, MAX(window_end_time)), 0) AS base_time
        FROM {input_table}
    """)

    result = pd.read_sql(query, engine)

    if result.empty or pd.isna(result.loc[0, "base_time"]):
        raise ValueError("base_time??怨꾩궛?????놁뒿?덈떎. ?낅젰 ?뚯씠釉붿뿉 ?곗씠?곌? ?놁뒿?덈떎.")

    return pd.to_datetime(result.loc[0, "base_time"])


def load_inference_data(
    engine: Engine,
    input_table: str,
    base_time: pd.Timestamp,
) -> pd.DataFrame:
    query = text(f"""
        SELECT
            equipment_id AS unique_id,
            window_end_time AS ds,
            avg_activePower AS y,
            avg_current_r AS currentR,
            avg_current_s AS currentS,
            avg_current_t AS currentT
        FROM {input_table}
        WHERE window_end_time >= DATEADD(DAY, -7, :base_time)
          AND window_end_time <= :base_time
        ORDER BY equipment_id, window_end_time
    """)

    df = pd.read_sql(query, engine, params={"base_time": base_time})

    if df.empty:
        raise ValueError("異붾줎???곗씠?곌? 鍮꾩뼱 ?덉뒿?덈떎.")

    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = pd.to_numeric(df["y"], errors="coerce")

    df = df.dropna(subset=["unique_id", "ds", "y"])
    df = df.sort_values(["unique_id", "ds"]).reset_index(drop=True)

    return df


def save_forecast_result(
    engine: Engine,
    output_table: str,
    result_df: pd.DataFrame,
) -> None:
    if result_df.empty:
        raise ValueError("??ν븷 ?덉륫 寃곌낵媛 ?놁뒿?덈떎.")

    result_df.to_sql(
        name=output_table.split(".")[-1],
        con=engine,
        schema=output_table.split(".")[0] if "." in output_table else None,
        if_exists="append",
        index=False,
        method=None,
    )

