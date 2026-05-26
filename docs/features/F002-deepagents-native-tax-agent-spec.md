---
feature_ids: [F002]
related_features: [F001]
topics: [deepagents, tax-agent, planning, rag, agentic-rag]
doc_kind: spec
created: 2026-05-26
---

# F002: DeepAgents-Native Tax Agent Refinement

> Status: spec | Owner: TBD

## Why

F001 proved that the POC can run DeepAgents examples and a tax-agent E2E pipeline. However, several concepts in Part 2 are currently implemented as project-level adapters:

- intent classification is a pre-agent business taxonomy
- planning is a static template selected by intent
- RAG is a no-op decorator placeholder

The next phase should make Part 2 closer to DeepAgents' native execution model, especially native planning and agentic retrieval.

## What

Refactor the Part 2 tax agent so the core reasoning loop is driven by DeepAgents rather than by static precomputed plans.

### In Scope

1. Replace static planner-driven prompt construction with a DeepAgents-native planning path.
   - The agent should be instructed to decompose work using its native planning behavior.
   - Runtime verification should capture evidence that the agent used planning, for example `write_todos` tool events in streaming output.

2. Replace the no-op RAG decorator with an actual retrieval tool.
   - Register a retrieval tool through `create_deep_agent(tools=[...])`.
   - Start with a small local tax knowledge corpus committed in the repo.
   - Retrieval results must include source identifiers that can become structured citations.

3. Reposition intent classification.
   - Keep `definition` / `rate` / `compliance` as business report metadata if useful.
   - Do not use the classifier as the main planner switch.
   - Do not describe intent classification as DeepAgents-native.

4. Improve output quality.
   - Strip model reasoning tags such as `<think>...</think>` from final Markdown/JSON.
   - Populate JSON `citations` from retrieved sources when retrieval is used.
   - Preserve Markdown and JSON outputs as the public artifacts.

### Out of Scope

- Production-grade tax-law knowledge base.
- External vector database or hosted RAG service.
- Expert legal/tax validation.
- Full local Ollama/vLLM rerun unless separately requested.

## Acceptance Criteria

1. [ ] Concept record exists and clearly distinguishes DeepAgents-native capabilities from project adapters.
2. [ ] Part 2 no longer depends on static `DefaultPlanner` templates to drive answer execution.
3. [ ] At least one Part 2 runtime verification captures DeepAgents-native planning evidence, such as `write_todos` tool events.
4. [ ] RAG is implemented as a registered DeepAgents tool, not as a post-answer no-op decorator.
5. [ ] Retrieval-backed answers include structured citation metadata in JSON output.
6. [ ] Final Markdown/JSON outputs do not contain leaked reasoning tags such as `<think>...</think>`.
7. [ ] Existing tests pass, and new tests cover planner removal, retrieval tool registration, citation extraction, and reasoning-tag cleanup.
8. [ ] E2E validation produces a Markdown report and JSON report from `sample_input.txt`.

## Dependencies

- `deepagents >= 0.6.3`
- MiniMax OpenAI-compatible runtime used in F001 validation
- Existing Part 2 modules:
  - `question_extractor.py`
  - `intent_classifier.py`
  - `planner.py`
  - `rag_decorator.py`
  - `agent_executor.py`
  - `output_formatter.py`

## Proposed Architecture

```text
sample_input.txt / input.docx
  -> question_extractor
  -> optional intent metadata
  -> AgentExecutor
       -> create_deep_agent(
            tools=[retrieve_tax_context],
            system_prompt=tax prompt with planning + citation rules
          )
       -> native planning/tool loop
  -> output_formatter
       -> strip reasoning tags
       -> Markdown
       -> JSON with citations
```

## Implementation Notes

### Planning

The static `Planner` can be kept temporarily for compatibility, but the main E2E path should stop injecting static plan steps into the user prompt.

Preferred runtime evidence:

- use `agent.stream(..., version="v2")` or `agent.stream_events(..., version="v3")`
- capture tool events
- assert at least one planning-related event appears for a multi-step tax question

### Retrieval Tool

Start with a simple local tool:

```python
def retrieve_tax_context(query: str) -> list[dict]:
    return [
        {
            "source_id": "vat-temporary-regulations",
            "title": "中华人民共和国增值税暂行条例",
            "snippet": "...",
        }
    ]
```

This is enough to prove the DeepAgents tool path without introducing a vector database.

### Output Formatting

The formatter should treat citations as structured data, not only text inside the model answer.

Minimum JSON shape:

```json
{
  "question": "...",
  "intent": "definition",
  "answer": "...",
  "citations": [
    {
      "source_id": "vat-temporary-regulations",
      "title": "中华人民共和国增值税暂行条例"
    }
  ]
}
```

## Risk

- Tool-calling behavior depends on model compliance. Runtime tests should use prompts that make retrieval necessary.
- DeepAgents event formats may vary by `stream` / `stream_events` version. Tests should isolate event parsing behind a small helper.
- A small local corpus can prove mechanics but not tax-law completeness.

## Open Questions

- Should intent classification remain before agent execution only for reporting, or move after answer generation as output metadata?
- Should F002 remove `Planner` entirely or keep it as a legacy adapter with tests proving it is not used in the main path?
- Should the first retrieval corpus be handcrafted tax snippets or generated from public legal references?
