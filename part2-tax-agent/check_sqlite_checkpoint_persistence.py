"""Validate local SQLite checkpoint persistence without OpenGauss.

This is a local readiness check for the checkpoint call chain. It does not
replace the final OpenGauss acceptance test.

Usage:
    python check_sqlite_checkpoint_persistence.py
    python check_sqlite_checkpoint_persistence.py --output ./output --thread-id demo-thread
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TypedDict

SERVICE_SQLITE_FILENAME = "service.sqlite"


class DemoState(TypedDict):
    messages: list[str]


def _load_sqlite_saver():
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "langgraph-checkpoint-sqlite is required. "
            "Install project dependencies, then rerun this script."
        ) from exc
    return SqliteSaver


def _build_demo_graph(checkpointer):
    from langgraph.graph import END, START, StateGraph

    def append_checkpoint_marker(state: DemoState) -> DemoState:
        return {"messages": [*state.get("messages", []), "checkpoint-ok"]}

    builder = StateGraph(DemoState)
    builder.add_node("append_checkpoint_marker", append_checkpoint_marker)
    builder.add_edge(START, "append_checkpoint_marker")
    builder.add_edge("append_checkpoint_marker", END)
    return builder.compile(checkpointer=checkpointer)


def _sqlite_checkpoint_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / "checkpoints" / SERVICE_SQLITE_FILENAME


def verify_sqlite_checkpoint(output_dir: str | Path, thread_id: str) -> dict:
    sqlite_saver = _load_sqlite_saver()
    db_path = _sqlite_checkpoint_path(output_dir)
    checkpoint_dir = db_path.parent
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    config = {"configurable": {"thread_id": thread_id}}

    with sqlite_saver.from_conn_string(str(db_path)) as checkpointer:
        if hasattr(checkpointer, "setup"):
            checkpointer.setup()
        graph = _build_demo_graph(checkpointer)
        first_output = graph.invoke({"messages": ["first-run"]}, config=config)
        first_history_count = len(list(graph.get_state_history(config)))

    with sqlite_saver.from_conn_string(str(db_path)) as reopened:
        graph = _build_demo_graph(reopened)
        restored_state = graph.get_state(config)
        restored_history_count = len(list(graph.get_state_history(config)))

    values = getattr(restored_state, "values", {}) or {}
    restored_messages = values.get("messages", [])
    if restored_messages != first_output["messages"]:
        raise RuntimeError(
            "SQLite checkpoint restore mismatch: "
            f"expected {first_output['messages']!r}, got {restored_messages!r}"
        )
    if restored_history_count < first_history_count or restored_history_count == 0:
        raise RuntimeError("SQLite checkpoint history was not restored")

    return {
        "backend": "sqlite",
        "thread_id": thread_id,
        "path": str(db_path),
        "state_messages": restored_messages,
        "history_count": restored_history_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate SQLite checkpoint persistence")
    parser.add_argument("--output", default="./output", help="Output directory")
    parser.add_argument("--thread-id", default="sqlite-checkpoint-demo", help="Checkpoint thread_id")
    args = parser.parse_args(argv)

    try:
        result = verify_sqlite_checkpoint(args.output, args.thread_id)
    except RuntimeError as exc:
        print(f"SQLite checkpoint verification: skipped - {exc}")
        return 2
    except Exception as exc:
        print(f"SQLite checkpoint verification: failed - {type(exc).__name__}: {exc}")
        return 1

    print("SQLite checkpoint verification: ok")
    print(f"  backend: {result['backend']}")
    print(f"  thread_id: {result['thread_id']}")
    print(f"  path: {result['path']}")
    print(f"  history_count: {result['history_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
