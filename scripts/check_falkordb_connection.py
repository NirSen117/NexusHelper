"""Check the configured FalkorDB connection without changing graph data."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.settings import settings  # noqa: E402
from falkordb import FalkorDB  # noqa: E402


def main() -> int:
    client = None
    try:
        client = FalkorDB(
            host=settings.falkordb_host,
            port=settings.falkordb_port,
            username=settings.falkordb_username,
            password=settings.falkordb_password,
            ssl=settings.falkordb_use_tls,
        )
        graph = client.select_graph(settings.falkordb_graph)
        result = graph.query("RETURN 1 AS ping")
        headers = [
            next((part for part in item if isinstance(part, str)), item[0])
            if isinstance(item, (list, tuple)) and item
            else item
            for item in result.header
        ]
        rows = [dict(zip(headers, row)) for row in result.result_set]
        if rows and rows[0].get("ping") == 1:
            print(f"FalkorDB connection OK; graph '{settings.falkordb_graph}' is reachable.")
            return 0
        print("FalkorDB responded, but the ping result was unexpected.")
        return 1
    except Exception as exc:
        print(f"FalkorDB connection failed ({type(exc).__name__}).")
        print("Check host, port, username, password, and TLS in the local backend .env.")
        return 1
    finally:
        connection = getattr(client, "connection", None)
        if connection is not None and hasattr(connection, "close"):
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
