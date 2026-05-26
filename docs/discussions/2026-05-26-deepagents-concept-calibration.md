---
feature_ids: [F001, F002]
topics: [deepagents, planning, intent-classification, rag, tax-agent]
doc_kind: discussion
created: 2026-05-26
---

# DeepAgents Concept Calibration

## Purpose

Before starting the next phase, we clarified three overloaded terms in the current E2E flow:

- intent classification
- planning
- RAG

The goal is to separate DeepAgents-native capabilities from project adapters and demo-only scaffolding.

## Source Anchors

- DeepAgents overview: planning and task decomposition, subagents, filesystem, memory, HITL.
  <https://docs.langchain.com/oss/python/deepagents/overview>
- DeepAgents context engineering and memory: context is managed through filesystem, memory files, store-backed state, and tools.
  <https://docs.langchain.com/oss/python/deepagents/context-engineering>
  <https://docs.langchain.com/oss/python/deepagents/memory>
- LangChain retrieval/RAG: retrieval augments generation with runtime external knowledge and may be two-step or agentic.
  <https://docs.langchain.com/oss/python/langchain/retrieval>

## Concept Comparison

| Concept | DeepAgents / LangChain meaning | Current project meaning | Classification | Gap |
|---|---|---|---|---|
| Intent classification | Not a standalone DeepAgents-native primitive. It can be implemented as model reasoning, a tool, structured output, or app-level routing. | `IntentClassifier` maps a tax question to `definition`, `rate`, or `compliance` before the agent runs. | Project adapter | We should not describe it as a DeepAgents feature. |
| Planning | DeepAgents-native task decomposition via built-in planning behavior such as `write_todos`, where the agent can create and update task state during execution. | `Planner` returns a static three-step template based on the intent label, then injects it into the user prompt. | Demo scaffold / project adapter | It demonstrates a planning-like UX, but not DeepAgents-native planning. |
| RAG | LangChain retrieval pattern. In a DeepAgents-style agent, retrieval should usually be exposed as a tool or context source the agent can call when needed. | `RAGDecorator` exposes a future adapter interface, but the default `NoopRAG` returns no documents. | Placeholder adapter | Current E2E does not perform real retrieval-augmented generation. |

## Current E2E Interpretation

The current Part 2 E2E flow verifies this pipeline:

```text
input text
  -> question extraction
  -> project-level intent classification
  -> static project planner
  -> DeepAgents answer execution
  -> optional no-op RAG decoration
  -> Markdown/JSON output
```

This is a valid POC pipeline, but only the answer execution step is directly backed by DeepAgents in Part 2.

## Recommended Next Direction

For the next phase, move Part 2 closer to DeepAgents by changing the pipeline shape:

```text
input text
  -> question extraction
  -> DeepAgents agent with native planning + retrieval tool
  -> output formatter
```

Intent classification can remain as report metadata, but it should not be used to claim DeepAgents-native routing or planning.

RAG should become an actual retrieval tool registered with `create_deep_agent(tools=[...])`, not a no-op decorator after answer generation.

## Known Output Quality Findings

The current generated output proves the pipeline runs, but it also shows two quality gaps:

- model reasoning tags such as `<think>...</think>` leak into the final report
- JSON `citations` arrays are empty even when the answer body contains legal basis text

These are not blockers for the F001 POC, but they should be addressed before demo-quality output or external review.
