"""Checkpoint backend selection for the tax agent runtime.

Main path:
    AgentExecutor.create(...) -> build_async_checkpoint_config(...)

Compatibility path:
    AgentExecutor(...) -> build_checkpoint_config(...)

OpenGauss is intentionally kept in the synchronous compatibility factory only.
The current local runtime uses SQLite first and falls back to memory when the
SQLite package is unavailable.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid


def _safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)


@dataclass
class CheckpointConfig:
    checkpointer: Any
    backend_type: str
    thread_id: str
    path: str | None = None

    @property
    def invoke_config(self) -> dict:
        return {"configurable": {"thread_id": self.thread_id}}

    def invoke_config_for(
        self,
        thread_id: str | None = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
        callbacks: list | None = None,
    ) -> dict:
        config: dict = {"configurable": {"thread_id": thread_id or self.thread_id}}
        if metadata:
            config["metadata"] = metadata
        if tags:
            config["tags"] = tags
        if callbacks:
            config["callbacks"] = callbacks
        return config


async def build_async_checkpoint_config(
    output_dir: str | Path,
    run_id: str | None = None,
    backend_type: str | None = None,
    dsn: str | None = None,
) -> CheckpointConfig:
    del dsn
    thread_id = run_id or f"tax-run-{uuid.uuid4().hex}"
    backend_type = backend_type or "auto"
    if backend_type not in {"auto", "sqlite", "memory"}:
        raise ValueError(f"Unsupported checkpoint backend: {backend_type}")

    checkpoint_dir = Path(output_dir) / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = checkpoint_dir / f"{_safe_filename(thread_id)}.sqlite"

    try:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        conn = await aiosqlite.connect(str(sqlite_path))
        return CheckpointConfig(
            checkpointer=AsyncSqliteSaver(conn),
            backend_type="sqlite",
            thread_id=thread_id,
            path=str(sqlite_path),
        )
    except Exception:
        try:
            import sqlite3
            from langgraph.checkpoint.sqlite import SqliteSaver

            conn = sqlite3.connect(str(sqlite_path), check_same_thread=False)
            return CheckpointConfig(
                checkpointer=SqliteSaver(conn),
                backend_type="sqlite",
                thread_id=thread_id,
                path=str(sqlite_path),
            )
        except Exception:
            if backend_type == "sqlite":
                raise
            from langgraph.checkpoint.memory import InMemorySaver

            return CheckpointConfig(
                checkpointer=InMemorySaver(),
                backend_type="memory",
                thread_id=thread_id,
                path=None,
            )


def build_checkpoint_config(
    output_dir: str | Path,
    run_id: str | None = None,
    backend_type: str | None = None,
    dsn: str | None = None,
) -> CheckpointConfig:
    thread_id = run_id or f"tax-run-{uuid.uuid4().hex}"
    backend_type = backend_type or "auto"
    if backend_type == "opengauss":
        if not dsn:
            raise RuntimeError("OPENGAUSS_DSN is required when CHECKPOINT_BACKEND=opengauss")
        try:
            from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "CHECKPOINT_BACKEND=opengauss requires langgraph-checkpoint-postgres"
            ) from exc

        return CheckpointConfig(
            checkpointer=PostgresSaver.from_conn_string(dsn),
            backend_type="opengauss",
            thread_id=thread_id,
            path=dsn,
        )

    if backend_type not in {"auto", "sqlite", "memory"}:
        raise ValueError(f"Unsupported checkpoint backend: {backend_type}")

    checkpoint_dir = Path(output_dir) / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = checkpoint_dir / f"{_safe_filename(thread_id)}.sqlite"

    if backend_type == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        return CheckpointConfig(
            checkpointer=InMemorySaver(),
            backend_type="memory",
            thread_id=thread_id,
            path=None,
        )

    try:
        import aiosqlite  # type: ignore
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # type: ignore

        return CheckpointConfig(
            checkpointer=AsyncSqliteSaver.from_conn_string(str(sqlite_path)),
            backend_type="sqlite",
            thread_id=thread_id,
            path=str(sqlite_path),
        )
    except Exception:
        try:
            import sqlite3
            from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore

            conn = sqlite3.connect(str(sqlite_path), check_same_thread=False)
            return CheckpointConfig(
                checkpointer=SqliteSaver(conn),
                backend_type="sqlite",
                thread_id=thread_id,
                path=str(sqlite_path),
            )
        except Exception:
            if backend_type == "sqlite":
                raise
            from langgraph.checkpoint.memory import InMemorySaver

            return CheckpointConfig(
                checkpointer=InMemorySaver(),
                backend_type="memory",
                thread_id=thread_id,
                path=None,
            )
