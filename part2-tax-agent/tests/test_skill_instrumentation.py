"""Skill instrumentation tests (red-first).

These tests lock down the contract for F004-stage skill observability:

- ``ExecutionResult.skills_invoked`` / ``skill_invocation_count`` capture the
  *real* ``read_file`` invocations the model made against the skills tree
  (paths of the form ``/skills/<name>/...``).
- ``_collect_tool_events`` keeps the legacy ``{"name": ...}`` shape and
  adds ``tool_type`` and (optionally) ``args`` for downstream consumers.
- ``ObservabilityConfig.record_skill_invocation`` forwards a structured
  ``skill.invocation`` event to the Langfuse ``event_recorder`` with the
  tags / metadata downstream filters rely on.

The test does not exercise the live Langfuse SDK; it substitutes an
``event_recorder`` mock so the contract is testable without network.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from tax_agent.runtime.agent_executor import AgentExecutor, ExecutionResult
from tax_agent.runtime.observability import ObservabilityConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FakeToolCall:
    """Mimic of langchain_core.messages.AIMessage.tool_calls entries."""

    name: str
    args: dict[str, Any]
    id: str = "tc-fake"


def _ai_message_with_tool_calls(*calls: _FakeToolCall) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"name": c.name, "args": c.args, "id": c.id} for c in calls],
    }


def _tool_message(name: str, content: str = "ok") -> dict:
    return {"role": "tool", "name": name, "content": content}


# ---------------------------------------------------------------------------
# _extract_skill_invocations
# ---------------------------------------------------------------------------


def test_extract_skill_invocations_single_skill_dedup():
    messages = [
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/skills/audit-intent-inference/SKILL.md"}),
        ),
        _tool_message("read_file"),
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/skills/audit-intent-inference/SKILL.md", "limit": 200}),
        ),
        _tool_message("read_file"),
    ]

    invoked = AgentExecutor._extract_skill_invocations(messages)

    assert invoked == ["audit-intent-inference"]
    assert AgentExecutor._count_skill_invocations(messages) == 2


def test_extract_skill_invocations_preserves_first_seen_order():
    messages = [
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/skills/solution-generation/SKILL.md"}),
        ),
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/skills/audit-intent-inference/SKILL.md"}),
        ),
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/skills/solution-generation/refs/extra.md"}),
        ),
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/skills/tax-finance-logic-decomposition/SKILL.md"}),
        ),
    ]

    invoked = AgentExecutor._extract_skill_invocations(messages)

    assert invoked == [
        "solution-generation",
        "audit-intent-inference",
        "tax-finance-logic-decomposition",
    ]


def test_extract_skill_invocations_ignores_non_skill_paths():
    messages = [
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/memories/AGENTS.md"}),
        ),
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/tmp/foo.txt"}),
        ),
        _ai_message_with_tool_calls(
            _FakeToolCall("retrieve_tax_context", {"query": "小型微利企业"}),
        ),
    ]

    assert AgentExecutor._extract_skill_invocations(messages) == []
    assert AgentExecutor._count_skill_invocations(messages) == 0


def test_extract_skill_invocations_handles_object_messages():
    """The executor accepts both dict and object messages."""

    @dataclass
    class _Msg:
        role: str
        content: str = ""
        name: str | None = None
        tool_calls: list[dict] = field(default_factory=list)

    messages = [
        _Msg(
            role="assistant",
            tool_calls=[{"name": "read_file", "args": {"file_path": "/skills/historical-question-matching/SKILL.md"}, "id": "x"}],
        ),
    ]

    assert AgentExecutor._extract_skill_invocations(messages) == [
        "historical-question-matching"
    ]


# ---------------------------------------------------------------------------
# _collect_tool_events (legacy shape + new classification)
# ---------------------------------------------------------------------------


def test_collect_tool_events_keeps_legacy_name_field():
    messages = [
        _tool_message("retrieve_tax_context"),
        _tool_message("analyze_tax_question"),
    ]

    events = AgentExecutor._collect_tool_events(messages)

    # Legacy contract: every event has a ``name`` field. The new
    # ``tool_type`` field is *additive* — it is allowed to appear.
    assert [e["name"] for e in events] == ["retrieve_tax_context", "analyze_tax_question"]
    assert all("name" in e for e in events)


def test_collect_tool_events_classifies_skill_type():
    messages = [
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/skills/audit-scenario-recognition/SKILL.md"}),
        ),
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/memories/AGENTS.md"}),
        ),
        _ai_message_with_tool_calls(
            _FakeToolCall("retrieve_tax_context", {"query": "小型微利企业"}),
        ),
    ]
    # Also include the tool messages so the events list sees the tool name.
    messages += [
        _tool_message("read_file"),
        _tool_message("read_file"),
        _tool_message("retrieve_tax_context"),
    ]

    events = AgentExecutor._collect_tool_events(messages)

    types = [e.get("tool_type") for e in events]
    names = [e.get("name") for e in events]

    # All three read_file pairs (ai+tool) collapse to one event each,
    # but the (ai, tool) pair yields two "tool" entries — one of which
    # classifies as skill, the other as other. We assert at least:
    assert "skill" in types, f"expected at least one skill event in {events!r}"
    assert "tax" in types, f"expected at least one tax event in {events!r}"
    assert "other" in types, f"expected at least one non-skill read_file in {events!r}"

    # First read_file (skill path) is the one that carries file_path args.
    skill_events = [e for e in events if e.get("tool_type") == "skill"]
    assert skill_events, "expected skill event with args.file_path"
    assert skill_events[0]["args"]["file_path"].endswith("SKILL.md")
    # Skill name derived from path.
    assert "skill_name" in skill_events[0]
    assert skill_events[0]["skill_name"] == "audit-scenario-recognition"

    # Legacy name field preserved on every event.
    assert all("name" in e for e in events), events


# ---------------------------------------------------------------------------
# ExecutionResult contract
# ---------------------------------------------------------------------------


def test_execution_result_default_skill_fields():
    result = ExecutionResult(answer="x")

    assert result.skills_invoked == []
    assert result.skill_invocation_count == 0


def test_execution_result_accepts_skill_fields():
    result = ExecutionResult(
        answer="x",
        skills_invoked=["audit-intent-inference"],
        skill_invocation_count=1,
    )

    assert result.skills_invoked == ["audit-intent-inference"]
    assert result.skill_invocation_count == 1


# ---------------------------------------------------------------------------
# ObservabilityConfig.record_skill_invocation
# ---------------------------------------------------------------------------


@dataclass
class _RecordedEvent:
    name: str
    input: Any = None
    output: Any = None
    metadata: dict | None = None
    tags: list[str] | None = None
    level: str = "DEFAULT"
    status_message: str | None = None


def test_record_skill_invocation_calls_event_recorder_with_tags():
    recorded: list[_RecordedEvent] = []

    def _recorder(**kwargs) -> None:
        recorded.append(_RecordedEvent(**kwargs))

    cfg = ObservabilityConfig(
        provider="langfuse",
        callbacks=["fake"],
        event_recorder=_recorder,
        base_tags=["tax-agent"],
    )

    cfg.record_skill_invocation(
        skill_name="audit-scenario-recognition",
        file_path="/skills/audit-scenario-recognition/SKILL.md",
        session_id="sess-1",
        trace_id="trace-1",
        thread_id="thread-1",
        duration_ms=42,
    )

    assert len(recorded) == 1
    evt = recorded[0]
    assert evt.name == "skill.invocation"
    assert "skill_invocation=true" in (evt.tags or [])
    assert "skill_name=audit-scenario-recognition" in (evt.tags or [])
    assert "tax-agent" in (evt.tags or [])
    assert evt.metadata is not None
    assert evt.metadata["skill_name"] == "audit-scenario-recognition"
    assert evt.metadata["file_path"] == "/skills/audit-scenario-recognition/SKILL.md"
    assert evt.metadata["session_id"] == "sess-1"
    assert evt.metadata["thread_id"] == "thread-1"
    assert evt.metadata["duration_ms"] == 42


def test_record_skill_invocation_is_noop_when_event_recorder_missing():
    cfg = ObservabilityConfig(provider="langfuse", callbacks=["fake"], event_recorder=None)

    # Must not raise even though there is nowhere to send the event.
    cfg.record_skill_invocation(
        skill_name="x",
        file_path="/skills/x/SKILL.md",
    )


# ---------------------------------------------------------------------------
# Exploratory tool subtype (B1)
# ---------------------------------------------------------------------------


def test_collect_tool_events_marks_ls_grep_glob_as_exploratory():
    messages = [
        _ai_message_with_tool_calls(_FakeToolCall("ls", {"path": "/"})),
        _ai_message_with_tool_calls(_FakeToolCall("grep", {"pattern": "foo", "path": "/tax_agent", "output_mode": "files_with_matches"})),
        _ai_message_with_tool_calls(_FakeToolCall("glob", {"pattern": "*.py"})),
    ]

    events = AgentExecutor._collect_tool_events(messages)

    names = [e["name"] for e in events]
    subtypes = [e.get("tool_subtype") for e in events]
    types = [e["tool_type"] for e in events]

    assert names == ["ls", "grep", "glob"]
    assert subtypes == ["exploratory", "exploratory", "exploratory"]
    # Exploratory tools are still ``other`` from the business perspective.
    assert types == ["other", "other", "other"]


def test_collect_tool_events_tax_tool_has_no_subtype():
    messages = [
        _ai_message_with_tool_calls(_FakeToolCall("retrieve_tax_context", {"query": "vat"})),
    ]

    events = AgentExecutor._collect_tool_events(messages)

    assert events[0]["tool_type"] == "tax"
    assert events[0].get("tool_subtype") is None


def test_collect_tool_events_skill_tool_has_no_exploratory_subtype():
    """A read_file against a skill path is ``tool_type=skill``, not exploratory."""
    messages = [
        _ai_message_with_tool_calls(
            _FakeToolCall("read_file", {"file_path": "/skills/audit-intent-inference/SKILL.md"})
        ),
    ]

    events = AgentExecutor._collect_tool_events(messages)

    assert events[0]["tool_type"] == "skill"
    assert events[0]["skill_name"] == "audit-intent-inference"
    assert events[0].get("tool_subtype") is None


# ---------------------------------------------------------------------------
# Stream-side tool events (C)
# ---------------------------------------------------------------------------


import asyncio
from typing import Any

from tax_agent.config import AgentConfig
from tax_agent.runtime.conversation import ConversationMessage, ConversationRequest


class _FakeStreamAgent:
    """Minimal astream_events stub: yields one tool.started then answer.finished."""

    def __init__(self, events: list[dict]) -> None:
        self._events = events
        self.version = "v2"
        self.config: dict = {}
        self.payload: dict = {}

    async def astream_events(self, payload, config=None, version="v2"):
        self.payload = payload
        self.config = config or {}
        self.version = version
        for ev in self._events:
            yield ev


def test_stream_turn_injects_tool_type_into_tool_started_event():
    fake = _FakeStreamAgent(
        events=[
            {
                "event": "on_tool_start",
                "name": "read_file",
                "data": {"input": {"file_path": "/skills/solution-generation/SKILL.md"}},
            },
            {
                "event": "on_tool_start",
                "name": "ls",
                "data": {"input": {"path": "/tax_agent"}},
            },
            {
                "event": "on_chain_end",
                "name": "agent",
                "data": {"output": {"messages": []}},
            },
        ]
    )
    executor = AgentExecutor(AgentConfig(), agent=fake)
    request = ConversationRequest(
        session_id="sess-stream-instr",
        trace_id="trace-stream-instr",
        thread_id="thread-stream-instr",
        messages=[ConversationMessage(role="user", content="ping")],
    )

    async def _collect() -> list:
        return [ev async for ev in executor.stream_turn(request)]

    events = asyncio.new_event_loop().run_until_complete(_collect())

    tool_started = [e for e in events if e.get("event") == "tool.started"]
    assert len(tool_started) == 2
    assert tool_started[0]["data"]["tool_type"] == "skill"
    assert tool_started[0]["data"]["skill_name"] == "solution-generation"
    assert tool_started[0]["data"]["name"] == "read_file"
    assert tool_started[1]["data"]["tool_type"] == "other"
    assert tool_started[1]["data"]["tool_subtype"] == "exploratory"
    assert tool_started[1]["data"]["name"] == "ls"


# ---------------------------------------------------------------------------
# System prompt mentions Skills (B2)
# ---------------------------------------------------------------------------


def test_tax_system_prompt_mandates_skill_lookahead():
    """B2: the system prompt must instruct the model to consult the Skills
    list before invoking any tool. This is a soft contract test — it locks
    the prompt wording so a future drive-by edit cannot silently drop the
    Skill discipline."""
    prompt = AgentExecutor.__module__ and __import__(
        "tax_agent.runtime.agent_executor", fromlist=["TAX_SYSTEM_PROMPT"]
    ).TAX_SYSTEM_PROMPT

    assert "Skills" in prompt or "skill" in prompt, "system prompt must mention skills"
    assert "read_file" in prompt, "system prompt must mention read_file as the mechanism"
    # ls/grep restriction is part of the same hard-coded discipline.
    assert "ls" in prompt and "grep" in prompt, (
        "system prompt must restrict ls/grep exploration against /tax_agent/"
    )


# ---------------------------------------------------------------------------
# V3: A (prompt budget) + B (recursion_limit)
# ---------------------------------------------------------------------------


def test_tax_system_prompt_caps_skill_reads_at_one():
    """V3 A: the prompt must explicitly cap skill reads to 1 to avoid
    the V2 explosion (9 read_file calls → GraphRecursionError)."""
    from tax_agent.runtime.agent_executor import TAX_SYSTEM_PROMPT

    # The cap is communicated via the literal "1 个" / "仅 1 个" phrasing.
    assert ("1 个" in TAX_SYSTEM_PROMPT) or ("仅 1 个" in TAX_SYSTEM_PROMPT), (
        "system prompt must cap skill reads to exactly one"
    )
    # And the "no traversal" prohibition.
    assert "不要再读其他 skill" in TAX_SYSTEM_PROMPT or "不要全选" in TAX_SYSTEM_PROMPT, (
        "system prompt must forbid reading multiple skills in one turn"
    )


def test_apply_recursion_limit_injects_default_when_absent():
    config = {"configurable": {"thread_id": "t1"}, "metadata": {"k": "v"}}

    bounded = AgentExecutor._apply_recursion_limit(config)

    assert bounded["recursion_limit"] == 50
    # Caller's config not mutated.
    assert "recursion_limit" not in config


def test_apply_recursion_limit_respects_existing_value():
    config = {"recursion_limit": 100}

    bounded = AgentExecutor._apply_recursion_limit(config)

    assert bounded["recursion_limit"] == 100


# ---------------------------------------------------------------------------
# V4: master fallback chain port (96f6897 + 7873f70 + a94ceaf semantics)
# ---------------------------------------------------------------------------


_UNUSABLE_PHRASES = {"待生成", "正在生成", "未生成", "暂无回答", "无回答", "分析结论已生成"}


@pytest.mark.parametrize("phrase", sorted(_UNUSABLE_PHRASES))
def test_is_unusable_answer_flags_known_placeholder_phrases(phrase):
    assert AgentExecutor._is_unusable_answer(phrase) is True


@pytest.mark.parametrize(
    "answer",
    [
        "小型微利企业的标准是年应纳税所得额不超过 100 万元",
        "根据《增值税暂行条例》，一般纳税人销售自己使用过的固定资产可以按 3% 征收率简易计税。",
        "答案是：免税。",
    ],
)
def test_is_unusable_answer_accepts_real_answers(answer):
    assert AgentExecutor._is_unusable_answer(answer) is False


def test_is_unusable_answer_flags_short_status_words():
    """Phrases ≤12 chars containing 已生成 / 已完成 are unusable."""
    assert AgentExecutor._is_unusable_answer("答案已生成") is True
    assert AgentExecutor._is_unusable_answer("分析已完成") is True
    # Long phrases containing those words are still acceptable.
    assert (
        AgentExecutor._is_unusable_answer("本次分析已生成详细的中文回答如下：……（≥30 字）")
        is False
    )


def test_is_unusable_answer_flags_tool_call_draft():
    draft = '[{"name": "find_tax_authorities", "parameters": {"query": "vat"}}]'
    assert AgentExecutor._is_unusable_answer(draft) is True


def test_first_usable_answer_skips_placeholders():
    candidate = AgentExecutor._first_usable_answer(
        "",
        "待生成",
        "答案已生成",
        "小型微利企业的标准是年应纳税所得额不超过 100 万元",
    )
    assert "小型微利企业" in candidate


def test_first_usable_answer_returns_empty_when_all_unusable():
    candidate = AgentExecutor._first_usable_answer("", "待生成", "暂无回答")
    assert candidate == ""


# ---------------------------------------------------------------------------
# stream_turn fallback chain (V4: stream-aggregated → last_assistant →
# structured_response via aget_state)
# ---------------------------------------------------------------------------


class _FakeAgentWithState:
    """Fake agent exposing both astream_events + aget_state + get_state."""

    def __init__(self, state: dict, events: list[dict] | None = None) -> None:
        self._state = state
        self._events = events or []
        self.config: dict = {}
        self.payload: dict = {}
        self.version: str = "v2"

    async def astream_events(self, payload, config=None, version="v2"):
        self.payload = payload
        self.config = config or {}
        self.version = version
        for ev in self._events:
            yield ev

    async def aget_state(self, config):
        return self._state

    def get_state(self, config):
        return self._state


def test_stream_turn_falls_back_to_structured_response_via_aget_state():
    """When stream aggregation yields no answer and final_messages have no
    assistant content, stream_turn should query aget_state and read
    structured_response.answer."""
    agent = _FakeAgentWithState(
        state={"values": {"structured_response": {"answer": "这是来自 structured_response 的最终回答"}}},
        events=[
            {
                "event": "on_tool_start",
                "name": "read_file",
                "data": {"input": {"file_path": "/skills/solution-generation/SKILL.md"}},
            },
            {
                "event": "on_chain_end",
                "name": "agent",
                "data": {"output": {"messages": []}},
            },
        ],
    )
    executor = AgentExecutor(AgentConfig(), agent=agent)
    request = ConversationRequest(
        session_id="sess-fb",
        trace_id="trace-fb",
        thread_id="thread-fb",
        messages=[ConversationMessage(role="user", content="ping")],
    )

    async def _collect() -> list:
        return [ev async for ev in executor.stream_turn(request)]

    events = asyncio.new_event_loop().run_until_complete(_collect())

    answer_finished = [e for e in events if e.get("event") == "answer.finished"]
    run_error = [e for e in events if e.get("event") == "run.error"]
    run_finished = [e for e in events if e.get("event") == "run.finished"]

    # Fallback succeeded: run.finished (not run.error), answer.finished with the
    # structured_response content.
    assert run_error == [], f"expected no run.error, got {run_error!r}"
    assert len(answer_finished) == 1, f"expected exactly one answer.finished, got {events!r}"
    assert "structured_response" in answer_finished[0]["data"]["answer"]
    # run.finished is the last event after fallback.
    assert run_finished, "expected run.finished after fallback"


def test_stream_turn_skips_unusable_placeholder_in_last_assistant():
    """If last_assistant_content is a known placeholder, do not pick it."""
    placeholder_msg = {"role": "assistant", "content": "待生成"}
    agent = _FakeAgentWithState(
        state={"values": {"structured_response": {"answer": "实际回答"}}},
        events=[
            {
                "event": "on_chain_end",
                "name": "agent",
                "data": {"output": {"messages": [placeholder_msg]}},
            },
        ],
    )
    executor = AgentExecutor(AgentConfig(), agent=agent)
    request = ConversationRequest(
        session_id="sess-fb-ph",
        trace_id="trace-fb-ph",
        thread_id="thread-fb-ph",
        messages=[ConversationMessage(role="user", content="ping")],
    )

    async def _collect() -> list:
        return [ev async for ev in executor.stream_turn(request)]

    events = asyncio.new_event_loop().run_until_complete(_collect())

    run_error = [e for e in events if e.get("event") == "run.error"]
    answer_finished = [e for e in events if e.get("event") == "answer.finished"]

    assert run_error == []
    assert len(answer_finished) == 1
    assert answer_finished[0]["data"]["answer"] == "实际回答"


# ---------------------------------------------------------------------------
# V5: stream "no answer emitted" → proactive aget_state fallback that
#      synthesises answer.started + answer.finished
# ---------------------------------------------------------------------------


def test_stream_turn_emits_answer_events_from_aget_state_when_stream_silent():
    """V5 scenario: model completed 4+ tool calls but never emitted any
    answer.delta / answer.started on the stream. The adapter must query
    aget_state for ``structured_response.answer`` and proactively yield
    ``answer.started`` + ``answer.finished`` events so the client gets a
    full payload (including ``skills_invoked``)."""
    agent = _FakeAgentWithState(
        state={"values": {"structured_response": {"answer": "这是来自 state 的兜底回答"}}},
        events=[
            {
                "event": "on_tool_start",
                "name": "read_file",
                "data": {"input": {"file_path": "/skills/audit-scenario-recognition/SKILL.md"}},
            },
            {
                "event": "on_tool_end",
                "name": "read_file",
                "data": {"output": "skill content..."},
            },
            {
                "event": "on_tool_start",
                "name": "retrieve_tax_context",
                "data": {"input": {"query": "vat"}},
            },
            {
                "event": "on_tool_end",
                "name": "retrieve_tax_context",
                "data": {"output": "{}"},
            },
            {
                "event": "on_chain_end",
                "name": "agent",
                "data": {"output": {"messages": []}},
            },
        ],
    )
    executor = AgentExecutor(AgentConfig(), agent=agent)
    request = ConversationRequest(
        session_id="sess-v5",
        trace_id="trace-v5",
        thread_id="thread-v5",
        messages=[ConversationMessage(role="user", content="ping")],
    )

    async def _collect() -> list:
        return [ev async for ev in executor.stream_turn(request)]

    events = asyncio.new_event_loop().run_until_complete(_collect())

    run_started = [e for e in events if e.get("event") == "run.started"]
    answer_started = [e for e in events if e.get("event") == "answer.started"]
    answer_finished = [e for e in events if e.get("event") == "answer.finished"]
    run_finished = [e for e in events if e.get("event") == "run.finished"]
    run_error = [e for e in events if e.get("event") == "run.error"]

    assert run_started, "expected run.started"
    assert run_error == [], f"expected no run.error, got {run_error!r}"
    # V5: answer.started is synthesised because the stream was silent.
    assert len(answer_started) == 1
    assert len(answer_finished) == 1
    assert run_finished, "expected run.finished after fallback"
    # answer.finished carries the structured_response content.
    assert answer_finished[0]["data"]["answer"] == "这是来自 state 的兜底回答"
    # Skill observability fields are still surfaced even though fallback.
    assert "skills_invoked" in answer_finished[0]["data"]
    assert "skill_invocation_count" in answer_finished[0]["data"]


def test_stream_turn_no_answer_no_state_raises_model_output_error():
    """V5 negative: stream silent AND aget_state returns nothing usable →
    emit run.error ModelOutputError (not silent success)."""
    agent = _FakeAgentWithState(
        state={"values": {}},  # no structured_response
        events=[
            {
                "event": "on_tool_start",
                "name": "ls",
                "data": {"input": {"path": "/"}},
            },
            {
                "event": "on_chain_end",
                "name": "agent",
                "data": {"output": {"messages": []}},
            },
        ],
    )
    executor = AgentExecutor(AgentConfig(), agent=agent)
    request = ConversationRequest(
        session_id="sess-v5-neg",
        trace_id="trace-v5-neg",
        thread_id="thread-v5-neg",
        messages=[ConversationMessage(role="user", content="ping")],
    )

    async def _collect() -> list:
        return [ev async for ev in executor.stream_turn(request)]

    events = asyncio.new_event_loop().run_until_complete(_collect())

    answer_finished = [e for e in events if e.get("event") == "answer.finished"]
    run_error = [e for e in events if e.get("event") == "run.error"]

    assert answer_finished == []
    assert len(run_error) == 1
    assert run_error[0]["data"]["error"] == "ModelOutputError"


def test_stream_turn_no_answer_state_placeholder_skipped():
    """V5: aget_state returns a known placeholder → still emit run.error,
    do NOT promote a placeholder to run.finished."""
    agent = _FakeAgentWithState(
        state={"values": {"structured_response": {"answer": "待生成"}}},
        events=[
            {
                "event": "on_chain_end",
                "name": "agent",
                "data": {"output": {"messages": []}},
            },
        ],
    )
    executor = AgentExecutor(AgentConfig(), agent=agent)
    request = ConversationRequest(
        session_id="sess-v5-ph",
        trace_id="trace-v5-ph",
        thread_id="thread-v5-ph",
        messages=[ConversationMessage(role="user", content="ping")],
    )

    async def _collect() -> list:
        return [ev async for ev in executor.stream_turn(request)]

    events = asyncio.new_event_loop().run_until_complete(_collect())

    answer_finished = [e for e in events if e.get("event") == "answer.finished"]
    run_error = [e for e in events if e.get("event") == "run.error"]

    assert answer_finished == []
    assert len(run_error) == 1


def test_execute_turn_falls_back_to_aget_state_when_structured_and_last_assistant_empty():
    """V5 /chat path: structured_answer is empty AND last_assistant_content
    is empty → try aget_state before raising ModelOutputError."""
    agent = _FakeAgentWithState(
        state={"values": {"structured_response": {"answer": "来自 aget_state 的回答"}}},
    )

    class _FakeExecuteAgent:
        def __init__(self, state):
            self._state = state
            self.payload = None
            self.config = None

        async def ainvoke(self, payload, config=None):
            self.payload = payload
            self.config = config
            # Return an empty assistant message so structured_response is empty
            # and last_assistant_content is empty too.
            return {"messages": [{"role": "assistant", "content": ""}]}

        async def aget_state(self, config):
            return self._state

        def get_state(self, config):
            return self._state

    from tax_agent.config import AgentConfig

    executor = AgentExecutor(AgentConfig(), agent=_FakeExecuteAgent(agent._state))
    request = ConversationRequest(
        session_id="sess-v5-chat",
        trace_id="trace-v5-chat",
        thread_id="thread-v5-chat",
        messages=[ConversationMessage(role="user", content="ping")],
    )

    async def _collect():
        return await executor.execute_turn(request)

    result = asyncio.new_event_loop().run_until_complete(_collect())

    # V5: execute_turn now consults aget_state; we expect a non-empty answer
    # pulled from structured_response.
    assert "来自 aget_state 的回答" in result.answer, (
        f"expected aget_state fallback answer, got {result.answer!r}"
    )
