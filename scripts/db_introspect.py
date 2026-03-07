#!/usr/bin/env python3
"""
Database Introspection Script (Step 1)
======================================
Connects to PostgreSQL via asyncpg and dumps the exact schema
for the `events` and `venues` tables from information_schema.

This output will be used to generate 100%-accurate Pydantic models.

Usage:
    1. Copy .env.example → .env and fill in your real DB credentials.
    2. pip install asyncpg python-dotenv
    3. python scripts/db_introspect.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TARGET_TABLES: list[str] = ["events", "venues"]

SCHEMA_QUERY = """
SELECT
    c.table_name,
    c.column_name,
    c.ordinal_position,
    c.data_type,
    c.udt_name,
    c.character_maximum_length,
    c.numeric_precision,
    c.numeric_scale,
    c.is_nullable,
    c.column_default
FROM information_schema.columns c
WHERE c.table_schema = 'public'
  AND c.table_name = ANY($1::text[])
ORDER BY c.table_name, c.ordinal_position;
"""

FK_QUERY = """
SELECT
    tc.table_name       AS source_table,
    kcu.column_name     AS source_column,
    ccu.table_name      AS target_table,
    ccu.column_name     AS target_column,
    tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema  = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema   = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema    = 'public'
  AND tc.table_name      = ANY($1::text[])
ORDER BY tc.table_name, kcu.ordinal_position;
"""

INDEX_QUERY = """
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename  = ANY($1::text[])
ORDER BY tablename, indexname;
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _separator(title: str) -> str:
    line = "=" * 72
    return f"\n{line}\n  {title}\n{line}"


def _format_column(row: asyncpg.Record) -> str:
    parts: list[str] = []
    parts.append(f"  {row['column_name']:<30}")
    parts.append(f"type={row['data_type']:<20}")

    udt = row["udt_name"]
    if udt and udt != row["data_type"]:
        parts.append(f"udt={udt:<16}")

    max_len = row["character_maximum_length"]
    if max_len is not None:
        parts.append(f"max_len={max_len}")

    precision = row["numeric_precision"]
    scale = row["numeric_scale"]
    if precision is not None:
        parts.append(f"precision={precision}")
    if scale is not None:
        parts.append(f"scale={scale}")

    parts.append(f"nullable={row['is_nullable']}")

    default = row["column_default"]
    if default is not None:
        parts.append(f"default={default}")

    return "  ".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def introspect() -> None:
    # Load .env from project root (one level up from scripts/)
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        print(f"[ERROR] .env not found at {env_path}")
        print("        Copy .env.example → .env and fill in your credentials.")
        sys.exit(1)

    load_dotenv(env_path)

    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_name = os.getenv("DB_NAME", "ThaiApp")
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASSWORD")

    print(f"[INFO] Connecting to {db_host}:{db_port}/{db_name}...")

    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass,
        )
    except Exception as exc:
        print(f"[ERROR] Connection failed: {exc}")
        sys.exit(1)

    try:
        # ── 1. Column definitions ────────────────────────────────────────
        rows = await conn.fetch(SCHEMA_QUERY, TARGET_TABLES)
        if not rows:
            print("[WARN] No columns found. Check that 'events' and 'venues' exist in the 'public' schema.")
            return

        current_table = None
        for row in rows:
            if row["table_name"] != current_table:
                current_table = row["table_name"]
                print(_separator(f"TABLE: {current_table}"))
            print(_format_column(row))

        # ── 2. Foreign keys ──────────────────────────────────────────────
        fk_rows = await conn.fetch(FK_QUERY, TARGET_TABLES)
        if fk_rows:
            print(_separator("FOREIGN KEYS"))
            for fk in fk_rows:
                print(
                    f"  {fk['source_table']}.{fk['source_column']}"
                    f"  →  {fk['target_table']}.{fk['target_column']}"
                    f"  ({fk['constraint_name']})"
                )

        # ── 3. Indexes ───────────────────────────────────────────────────
        idx_rows = await conn.fetch(INDEX_QUERY, TARGET_TABLES)
        if idx_rows:
            print(_separator("INDEXES"))
            for idx in idx_rows:
                print(f"  [{idx['tablename']}] {idx['indexname']}")
                print(f"    {idx['indexdef']}")

        # ── 4. Row counts ────────────────────────────────────────────────
        print(_separator("ROW COUNTS"))
        for tbl in TARGET_TABLES:
            count = await conn.fetchval(f'SELECT COUNT(*) FROM "{tbl}"')  # noqa: S608
            print(f"  {tbl}: {count} rows")

    finally:
        await conn.close()

    print("\n[OK] Introspection complete. Paste the full output above back to me.")


if __name__ == "__main__":
    asyncio.run(introspect())
