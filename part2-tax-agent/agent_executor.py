from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from deepagents.backends import FilesystemBackend

from audit_trace import build_checkpoint_config, CheckpointConfig
from config import AgentConfig
from domain_knowledge import analyze_tax_question
from intent_classifier import ClassifiedQuestion
from tax_retrieval import extract_citations_from_messages, retrieve_tax_context

PART2_ROOT = Path(__file__).resolve().parent
SKILL_SOURCES = ["/skills"]
MEMORY_SOURCES = ["/memories/AGENTS.md"]


TAX_SYSTEM_PROMPT = """你是一位专业的税务顾问专家。
你的任务是准确回答税务相关问题，包括：
1. 税务概念定义与解释
2. 税率计算与税额分析
3. 税务合规性判断

回答要求：
- 基于事实和税法规定
- 结构清晰，分点阐述
- 如引用法规或数据，标注来源
- 如不确定，明确说明局限性
- 对复杂问题先使用 DeepAgents 原生规划能力（write_todos）拆解任务
- 需要法规依据时调用 retrieve_tax_context 工具，并在回答中引用检索到的 source_id/title
- 不输出模型内部推理标签，例如 <think>...</think>
"""


class TaxCitation(BaseModel):
    source_id: str = Field(description="检索来源 ID")
    title: str = Field(description="检索来源标题")


class TaxAnswer(BaseModel):
    question: str = Field(description="原始税务问题")
    intent: str = Field(description="业务标签：definition/rate/compliance")
    answer: str = Field(description="面向用户的中文回答")
    citations: list[TaxCitation] = Field(default_factory=list, description="结构化引用来源")


@dataclass
class ExecutionResult:
    answer: str
    citations: list[dict] = field(default_factory=list)
    tool_events: list[dict] = field(default_factory=list)
    domain_analysis: dict = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)


class AgentExecutor:
    def __init__(self, config: AgentConfig, agent=None, checkpoint_config: CheckpointConfig | None = None):
        self._config = config
        self._checkpoint_config = checkpoint_config or build_checkpoint_config(config.output_dir)
        self._agent = agent or self.build_agent(config, checkpointer=self._checkpoint_config.checkpointer)

    @staticmethod
    def build_agent(config: AgentConfig, checkpointer=None):
        from deepagents import create_deep_agent

        model = init_chat_model(
            config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        return create_deep_agent(
            model=model,
            system_prompt=TAX_SYSTEM_PROMPT,
            tools=[retrieve_tax_context, analyze_tax_question],
            skills=SKILL_SOURCES,
            memory=MEMORY_SOURCES,
            backend=FilesystemBackend(root_dir=PART2_ROOT, virtual_mode=True),
            response_format=TaxAnswer,
            checkpointer=checkpointer,
        )

    async def execute(self, question: ClassifiedQuestion, plan_steps: list[str] | None = None) -> str:
        if plan_steps is None:
            return (await self.execute_with_evidence(question)).answer

        prompt = self._build_prompt(question, plan_steps)
        result = await self._ainvoke({"messages": [{"role": "user", "content": prompt}]})
        return self._last_content(result["messages"])

    async def execute_with_evidence(self, question: ClassifiedQuestion) -> ExecutionResult:
        prompt = self._build_native_prompt(question)
        result = await self._ainvoke({"messages": [{"role": "user", "content": prompt}]})
        messages = result["messages"]
        structured_answer, structured_citations = self._structured_result(result)
        citations = structured_citations or extract_citations_from_messages(messages)
        domain_analysis = analyze_tax_question(question.text)
        return ExecutionResult(
            answer=structured_answer or self._last_content(messages),
            citations=citations,
            tool_events=self._collect_tool_events(messages),
            domain_analysis=domain_analysis,
            skills=self._skills_from_domain_analysis(domain_analysis),
        )

    async def _ainvoke(self, payload: dict) -> dict:
        try:
            return await self._agent.ainvoke(payload, config=self._checkpoint_config.invoke_config)
        except TypeError:
            return await self._agent.ainvoke(payload)

    @staticmethod
    def _build_prompt(question: ClassifiedQuestion, plan_steps: list[str]) -> str:
        plan_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan_steps))
        return f"""请回答以下税务问题。

问题：{question.text}

意图类别：{question.intent}

执行计划：
{plan_text}

请按照计划逐步回答，最终给出结构化的答案。"""

    @staticmethod
    def _build_native_prompt(question: ClassifiedQuestion) -> str:
        return f"""请回答以下税务问题。

问题：{question.text}

业务标签：{question.intent}

请使用 DeepAgents 原生工作方式完成任务：
1. 对需要多步判断的问题，使用 write_todos 拆解并跟踪任务。
2. 需要法规依据、政策来源或税务定义时，调用 retrieve_tax_context。
3. 回答必须结构化，并引用检索工具返回的 source_id/title。
4. 对税审问题使用 analyze_tax_question 获取术语、场景、历史问题和质询意图分析。
5. 不要输出 <think>...</think> 或其他内部推理标签。"""

    @staticmethod
    def _last_content(messages: list[Any]) -> str:
        last = messages[-1]
        if isinstance(last, dict):
            return last.get("content", "")
        return getattr(last, "content", "")

    @staticmethod
    def _collect_tool_events(messages: list[Any]) -> list[dict]:
        events = []
        for message in messages:
            name = message.get("name") if isinstance(message, dict) else getattr(message, "name", None)
            if not name:
                continue
            events.append({"name": name})
        return events

    @staticmethod
    def _skills_from_domain_analysis(domain_analysis: dict) -> list[str]:
        skills = []
        if domain_analysis.get("intent_hypotheses"):
            skills.append("audit-intent-inference")
        if domain_analysis.get("terms"):
            skills.append("tax-finance-logic-decomposition")
        if domain_analysis.get("scenario_matches"):
            skills.append("audit-scenario-recognition")
        if domain_analysis.get("historical_references"):
            skills.append("historical-question-matching")
        if domain_analysis.get("scenario_matches") or domain_analysis.get("historical_references"):
            skills.append("solution-generation")
        return skills

    @staticmethod
    def _structured_result(result: dict) -> tuple[str, list[dict]]:
        structured = result.get("structured_response")
        if not structured:
            return "", []
        if isinstance(structured, BaseModel):
            data = structured.model_dump()
        elif isinstance(structured, dict):
            data = structured
        else:
            return "", []
        return data.get("answer", ""), data.get("citations", [])
