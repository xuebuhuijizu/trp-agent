"""Validate LangGraph PostgresSaver compatibility with a local OpenGauss DSN.

Usage:
    set OPENGAUSS_DSN=postgresql://user:password@localhost:5432/dbname
    python check_opengauss_compat.py
"""

import os
import sys


def main() -> int:
    dsn = os.getenv("OPENGAUSS_DSN")
    if not dsn:
        print("Step 1 dependency check: skipped")
        print("Step 2 connection/setup: skipped - OPENGAUSS_DSN is not set")
        return 2

    try:
        from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore
        import psycopg  # noqa: F401
    except Exception as exc:
        print(f"Step 1 dependency check: failed - {type(exc).__name__}: {exc}")
        return 2

    print("Step 1 dependency check: ok")

    try:
        with PostgresSaver.from_conn_string(dsn) as checkpointer:
            checkpointer.setup()
    except Exception as exc:
        print(f"Step 2 connection/setup: failed - {type(exc).__name__}: {exc}")
        return 1

    print("Step 2 connection/setup: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
