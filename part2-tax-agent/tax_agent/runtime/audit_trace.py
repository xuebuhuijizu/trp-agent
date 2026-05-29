"""Local JSONL audit trace recorder retained from F003.

This module is not on the current /chat or /chat/stream main path. Runtime
checkpoint selection lives in tax_agent.runtime.checkpointing.
"""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditTraceRecorder:
    def __init__(
        self,
        output_dir: str | Path,
        run_id: str,
        input_file: str,
        input_file_hash: str,
        model: str,
        checkpoint_backend: str,
        checkpoint_thread_id: str,
        checkpoint_path: str | None = None,
    ):
        self.output_dir = Path(output_dir)
        self.run_id = run_id
        self.started_monotonic = time.perf_counter()
        self.events: list[dict] = []
        self.summary = {
            "run_id": run_id,
            "started_at": _utc_now(),
            "input": {
                "file": input_file,
                "file_hash": input_file_hash,
            },
            "model": {"name": model},
            "checkpoint": {
                "enabled": True,
                "backend_type": checkpoint_backend,
                "thread_id": checkpoint_thread_id,
                "path": checkpoint_path,
            },
            "totals": {
                "questions": 0,
                "tool_calls": 0,
                "skills": 0,
                "errors": 0,
            },
            "output_paths": {},
        }
        self._append("run_started", None, input_file=input_file, input_file_hash=input_file_hash)

    @classmethod
    def start(
        cls,
        output_dir: str | Path,
        input_file: str,
        input_file_hash: str,
        model: str,
        checkpoint_backend: str,
        checkpoint_thread_id: str,
        checkpoint_path: str | None = None,
        run_id: str | None = None,
    ) -> "AuditTraceRecorder":
        return cls(
            output_dir=output_dir,
            run_id=run_id or f"tax-run-{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
            input_file=input_file,
            input_file_hash=input_file_hash,
            model=model,
            checkpoint_backend=checkpoint_backend,
            checkpoint_thread_id=checkpoint_thread_id,
            checkpoint_path=checkpoint_path,
        )

    def record_question_started(self, question_id: str, question: str, intent: str) -> None:
        self.summary["totals"]["questions"] += 1
        self._append("question_started", question_id, question=question, intent=intent)

    def record_skill_selected(self, question_id: str, skill_name: str, reason: str | None = None) -> None:
        self.summary["totals"]["skills"] += 1
        self._append("skill_selected", question_id, skill=skill_name, reason=reason)

    def record_tool_call(
        self,
        question_id: str,
        tool_name: str,
        args_summary: dict | None = None,
        source_ids: list[str] | None = None,
        latency_ms: int | None = None,
        error: str | None = None,
    ) -> None:
        self.summary["totals"]["tool_calls"] += 1
        if error:
            self.summary["totals"]["errors"] += 1
        self._append(
            "tool_call",
            question_id,
            tool_name=tool_name,
            args_summary=args_summary or {},
            source_ids=source_ids or [],
            latency_ms=latency_ms,
            error=error,
        )

    def record_answer(self, question_id: str, citations: list[dict], latency_ms: int | None = None) -> None:
        self._append(
            "structured_answer",
            question_id,
            source_ids=[citation.get("source_id") for citation in citations if isinstance(citation, dict)],
            citations=citations,
            latency_ms=latency_ms,
        )

    def record_error(self, question_id: str | None, error: Exception) -> None:
        self.summary["totals"]["errors"] += 1
        self._append("error", question_id, error_type=type(error).__name__, error=str(error))

    def finish(self, output_paths: dict[str, str]) -> dict[str, str]:
        elapsed_ms = int((time.perf_counter() - self.started_monotonic) * 1000)
        self.summary["finished_at"] = _utc_now()
        self.summary["latency_ms"] = elapsed_ms
        self.summary["output_paths"] = output_paths
        self._append("run_finished", None, latency_ms=elapsed_ms, output_paths=output_paths)

        audit_dir = self.output_dir / "audit_runs" / self.run_id
        audit_dir.mkdir(parents=True, exist_ok=True)
        trace_path = audit_dir / "trace.jsonl"
        summary_path = audit_dir / "trace.summary.json"
        trace_path.write_text(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in self.events) + "\n",
            encoding="utf-8",
        )
        summary_path.write_text(json.dumps(self.summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"trace": str(trace_path), "summary": str(summary_path)}

    def _append(self, event_type: str, question_id: str | None, **payload: Any) -> None:
        self.events.append(
            {
                "run_id": self.run_id,
                "question_id": question_id,
                "event_type": event_type,
                "timestamp": _utc_now(),
                **payload,
            }
        )
