import duckdb
import pandas as pd
from typing import Optional, List


class PowerDataLoader:
    def __init__(self, duckdb_path: str, table_name: str):
        self.duckdb_path = duckdb_path
        self.table_name = table_name

    def _connect(self):
        return duckdb.connect(self.duckdb_path, read_only=True)

    def get_sample(self, limit: int = 10) -> pd.DataFrame:
        query = f"""
        SELECT *
        FROM {self.table_name}
        ORDER BY timestamp, module
        LIMIT {limit}
        """

        with self._connect() as con:
            return con.execute(query).df()

    def get_next_chunk(
        self,
        last_timestamp: Optional[int],
        chunk_timestamps: int,
        end_timestamp: Optional[int] = None,
        modules: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        where_clauses = []

        if last_timestamp is not None:
            where_clauses.append(f"timestamp > {last_timestamp}")

        if end_timestamp is not None:
            where_clauses.append(f"timestamp <= {end_timestamp}")

        if modules:
            module_values = ", ".join([f"'{m}'" for m in modules])
            where_clauses.append(f"module IN ({module_values})")

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        query = f"""
        WITH next_timestamps AS (
            SELECT DISTINCT timestamp
            FROM {self.table_name}
            {where_sql}
            ORDER BY timestamp
            LIMIT {chunk_timestamps}
        )
        SELECT p.*
        FROM {self.table_name} p
        JOIN next_timestamps t
          ON p.timestamp = t.timestamp
        """

        if modules:
            module_values = ", ".join([f"'{m}'" for m in modules])
            query += f" WHERE p.module IN ({module_values})"

        query += """
        ORDER BY p.timestamp, p.module
        """

        with self._connect() as con:
            return con.execute(query).df()