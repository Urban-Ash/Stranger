#!/usr/bin/env python3
"""
列出数据库中所有用户表的列名与类型，并可选输出索引与扩展信息。

使用现有的配置管理与数据库连接（app.models.database.get_db）。

用法：
  python3 scripts/list_columns.py            # 人类可读输出
  python3 scripts/list_columns.py --json     # JSON 输出
  python3 scripts/list_columns.py --schema public  # 仅特定 schema
"""

import sys
import os
import json
import argparse
from typing import Dict, Any, List, Optional

# 确保项目根目录在导入路径中，便于独立运行
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from app.models.database import get_db, DatabaseError


def fetch_tables(conn, schema: Optional[str] = None) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        if schema:
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type='BASE TABLE'
                  AND table_schema = %s
                ORDER BY table_schema, table_name
                """,
                (schema,)
            )
        else:
            cur.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type='BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog','information_schema')
                ORDER BY table_schema, table_name
                """
            )
        rows = cur.fetchall() or []
        return [{"schema": r[0], "name": r[1]} for r in rows]


def fetch_columns(conn, schema: str, table: str) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            ORDER BY ordinal_position
            """,
            (schema, table)
        )
        rows = cur.fetchall() or []
        return [
            {"name": r[0], "type": r[1], "nullable": (r[2] == 'YES')}
            for r in rows
        ]


def fetch_indexes(conn, schema: str, table: str) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname=%s AND tablename=%s
            ORDER BY indexname
            """,
            (schema, table)
        )
        rows = cur.fetchall() or []
        return [{"name": r[0], "definition": r[1]} for r in rows]


def fetch_extensions(conn) -> List[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT extname FROM pg_extension ORDER BY extname")
        rows = cur.fetchall() or []
        return [r[0] for r in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="List all tables and columns")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--schema", type=str, default=None, help="Limit to a specific schema")
    args = parser.parse_args()

    try:
        conn = get_db()
    except DatabaseError as e:
        print(f"[ERROR] Database connection failed: {e}", file=sys.stderr)
        return 1

    tables = fetch_tables(conn, schema=args.schema)
    exts = fetch_extensions(conn)

    result: Dict[str, Any] = {
        "extensions": exts,
        "schemas": {}
    }

    for t in tables:
        schema = t["schema"]
        name = t["name"]
        cols = fetch_columns(conn, schema, name)
        idxs = fetch_indexes(conn, schema, name)
        result.setdefault("schemas", {}).setdefault(schema, {})[name] = {
            "columns": cols,
            "indexes": idxs,
        }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Detected extensions: {', '.join(exts) if exts else '(none)'}\n")
        for schema, tables_dict in result["schemas"].items():
            print(f"Schema: {schema}")
            for table_name, meta in tables_dict.items():
                print(f"  Table: {table_name}")
                for c in meta["columns"]:
                    null_flag = "NULL" if c["nullable"] else "NOT NULL"
                    print(f"    - {c['name']} ({c['type']}, {null_flag})")
                if meta["indexes"]:
                    print("    Indexes:")
                    for idx in meta["indexes"]:
                        print(f"      * {idx['name']}: {idx['definition']}")
                print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())