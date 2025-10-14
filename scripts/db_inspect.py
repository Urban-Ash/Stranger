import sys
import os
from typing import Any, Dict, List

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.models.database import get_db


def inspect_table(schema: str, table: str) -> Dict[str, Any]:
    conn = get_db()
    info: Dict[str, Any] = {"schema": schema, "table": table}
    with conn.cursor() as cur:
        # Row estimate
        cur.execute("SELECT reltuples::bigint FROM pg_class WHERE oid = %s::regclass", (f"{schema}.{table}",))
        r = cur.fetchone()
        info["row_estimate"] = (r[0] if r else None)

        # Columns and types
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        info["columns"] = [(c, t) for c, t in cur.fetchall() or []]

        # Indexes
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname=%s AND tablename=%s
            ORDER BY indexname
            """,
            (schema, table),
        )
        info["indexes"] = [(n, d) for n, d in cur.fetchall() or []]

        # Check phone expression index existence
        expr = "regexp_replace(CAST(phone AS TEXT), '[^0-9]', '', 'g')"
        cur.execute(
            """
            SELECT 1 FROM pg_indexes WHERE schemaname=%s AND tablename=%s AND indexdef LIKE %s
            """,
            (schema, table, f"%({expr})%"),
        )
        info["has_phone_expr_index"] = cur.fetchone() is not None

        # Sample explain plan for phone filter (may use seq scan)
        try:
            cur.execute("SET statement_timeout = 5000")
            cur.execute(
                f"EXPLAIN SELECT * FROM {schema}.{table} WHERE {expr} = %s LIMIT 5",
                ("17689273821",),
            )
            info["explain"] = [row[0] for row in cur.fetchall() or []]
        except Exception:
            info["explain"] = ["EXPLAIN failed or timed out"]

    return info


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "public.total_69"
    if "." in target:
        schema, table = target.split(".", 1)
    else:
        schema, table = "public", target
    info = inspect_table(schema, table)
    # Pretty print
    print("schema:", info["schema"]) 
    print("table:", info["table"]) 
    print("row_estimate:", info.get("row_estimate"))
    print("columns:")
    for c, t in info.get("columns", []):
        print(f"  - {c}: {t}")
    print("indexes:")
    for n, d in info.get("indexes", []):
        print(f"  - {n}: {d}")
    print("has_phone_expr_index:", info.get("has_phone_expr_index"))
    print("explain:")
    for line in info.get("explain", []):
        print("  ", line)


if __name__ == "__main__":
    main()