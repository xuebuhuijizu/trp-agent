"""Validate local Langfuse observability wiring.

This script does not store secrets. It reads LANGFUSE_* variables from the
process environment or from the project .env file loaded by python-dotenv.

Usage:
    python part2-tax-agent/check_langfuse_observability.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _masked(value: str | None) -> str:
    if not value:
        return "missing"
    if len(value) <= 10:
        return "***"
    return f"{value[:6]}...{value[-4:]}"


def _check_required_env() -> list[CheckResult]:
    required = {
        "LANGFUSE_PUBLIC_KEY": os.getenv("LANGFUSE_PUBLIC_KEY"),
        "LANGFUSE_SECRET_KEY": os.getenv("LANGFUSE_SECRET_KEY"),
        "LANGFUSE_BASE_URL": os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST"),
    }
    return [
        CheckResult(name, bool(value), _masked(value) if "KEY" in name else str(value or "missing"))
        for name, value in required.items()
    ]


def _check_health(base_url: str) -> CheckResult:
    health_url = base_url.rstrip("/") + "/api/public/health"
    try:
        with urlopen(health_url, timeout=5) as response:
            body = response.read().decode("utf-8", errors="replace")
            return CheckResult("langfuse_health", response.status == 200, body)
    except URLError as exc:
        return CheckResult("langfuse_health", False, str(exc))


def _check_callback_adapter() -> CheckResult:
    try:
        from tax_agent.runtime.observability import build_langfuse_observability

        observability = build_langfuse_observability(enabled=True)
        return CheckResult(
            "callback_adapter",
            observability.provider == "langfuse" and bool(observability.callbacks),
            f"provider={observability.provider}, callbacks={len(observability.callbacks)}",
        )
    except Exception as exc:
        return CheckResult("callback_adapter", False, f"{type(exc).__name__}: {exc}")


def _check_auth(base_url: str) -> CheckResult:
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            base_url=base_url,
        )
        ok = bool(client.auth_check())
        client.shutdown()
        return CheckResult("langfuse_auth", ok, "auth_check passed" if ok else "auth_check failed")
    except Exception as exc:
        return CheckResult("langfuse_auth", False, f"{type(exc).__name__}: {exc}")


def main() -> int:
    load_dotenv(ROOT / ".env")
    os.environ.setdefault("LANGFUSE_ENABLED", "1")

    base_url = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST") or ""
    results = _check_required_env()
    if base_url:
        results.append(_check_health(base_url))
        results.append(_check_auth(base_url))
    results.append(_check_callback_adapter())

    for result in results:
        status = "ok" if result.ok else "failed"
        print(f"{result.name}: {status} - {result.detail}")

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
