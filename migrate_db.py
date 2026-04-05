#!/usr/bin/env python3
"""
Manual database migration entrypoint.

This script is safe to run multiple times. It reuses DatabaseManager.init_db(),
which already contains the idempotent schema migration for legacy databases.
"""

import argparse
import os
import sqlite3
from typing import Dict, Set

from models import DatabaseManager


def get_table_columns(db_path: str, table_name: str) -> Set[str]:
    """Read existing column names from a SQLite table."""
    if not os.path.exists(db_path):
        return set()

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row[1] for row in rows}
    finally:
        conn.close()


def run_migration(db_path: str = "soar_mcp.db") -> Dict[str, object]:
    """Run idempotent schema migration and return a summary."""
    db_path = os.path.abspath(db_path)
    database_exists_before = os.path.exists(db_path)
    playbook_columns_before = get_table_columns(db_path, "playbooks")

    db_manager = DatabaseManager(db_path)
    db_manager.init_db()
    db_manager.engine.dispose()

    playbook_columns_after = get_table_columns(db_path, "playbooks")

    return {
        "dbPath": db_path,
        "databaseExistsBefore": database_exists_before,
        "playbookColumnsBefore": sorted(playbook_columns_before),
        "playbookColumnsAfter": sorted(playbook_columns_after),
        "resultFocusKeywordsAdded": (
            "result_focus_keywords" not in playbook_columns_before
            and "result_focus_keywords" in playbook_columns_after
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SOAR MCP database migration")
    parser.add_argument(
        "--db-path",
        default="soar_mcp.db",
        help="Path to the SQLite database file (default: soar_mcp.db)",
    )
    args = parser.parse_args()

    summary = run_migration(args.db_path)

    print("SOAR MCP database migration completed.")
    print(f"Database: {summary['dbPath']}")
    print(f"Database existed before migration: {summary['databaseExistsBefore']}")
    print(
        "Added playbooks.result_focus_keywords: "
        f"{summary['resultFocusKeywordsAdded']}"
    )
    print(
        "Current playbooks columns: "
        + ", ".join(summary["playbookColumnsAfter"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
