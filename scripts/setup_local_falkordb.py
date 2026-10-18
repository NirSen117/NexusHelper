"""Verify the local FalkorDB connection and load synthetic demo data if empty."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.settings import settings  # noqa: E402
from falkordb import FalkorDB  # noqa: E402


def rows(result: object) -> list[dict[str, object]]:
    headers = [
        (
            next((part for part in item if isinstance(part, str)), item[0])
            if isinstance(item, (list, tuple)) and item
            else item
        )
        for item in result.header  # type: ignore[attr-defined]
    ]
    return [
        dict(zip(headers, record))
        for record in result.result_set  # type: ignore[attr-defined]
    ]


def demo_seed_query() -> str:
    schema = (ROOT / "schema.cypher").read_text(encoding="utf-8")
    section = schema.split("// 2. SEED DATA", 1)[1].split(
        "// 3. PERMISSION-SCOPED QUERY TEMPLATES", 1
    )[0]
    match = re.search(r"(?m)^CREATE\s*$", section)
    if not match:
        raise RuntimeError("Could not locate the demo CREATE statement in schema.cypher")
    query = "\n".join(
        line for line in section[match.start() :].splitlines()
        if not line.lstrip().startswith("//")
    ).strip().rstrip(";")
    return query


def main() -> int:
    try:
        client = FalkorDB(
            host=settings.falkordb_host,
            port=settings.falkordb_port,
            username=settings.falkordb_username,
            password=settings.falkordb_password,
            ssl=settings.falkordb_use_tls,
        )
        graph = client.select_graph(settings.falkordb_graph)
        ping = rows(graph.query("RETURN 1 AS ping"))
        print(f"FalkorDB ping response: {ping!r}")
        if not ping or ping[0].get("ping") != 1:
            raise RuntimeError("FalkorDB ping returned an unexpected result")
        print(f"Connected to FalkorDB graph '{settings.falkordb_graph}'.")

        count_result = rows(graph.query("MATCH (n) RETURN count(n) AS nodes"))
        node_count = int(count_result[0]["nodes"]) if count_result else 0
        if node_count:
            print(f"Graph already contains {node_count} nodes; left its data unchanged.")
        else:
            graph.query(demo_seed_query())
            count_result = rows(graph.query("MATCH (n) RETURN count(n) AS nodes"))
            node_count = int(count_result[0]["nodes"]) if count_result else 0
            print(f"Loaded synthetic demo graph: {node_count} nodes.")
        print("Demo data is fictional; do not treat it as company records.")
        connection = getattr(client, "connection", None)
        if connection is not None and hasattr(connection, "close"):
            connection.close()
        return 0
    except Exception as exc:
        print(f"FalkorDB setup failed ({type(exc).__name__}). Check the running container and backend .env.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
