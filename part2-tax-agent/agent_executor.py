from config import AgentConfig
from intent_classifier import ClassifiedQuestion


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
"""


class AgentExecutor:
    def __init__(self, config: AgentConfig, agent=None):
        self._config = config
        self._agent = agent or self.build_agent(config)

    @staticmethod
    def build_agent(config: AgentConfig):
        from deepagents import create_deep_agent

        return create_deep_agent(
            model=config.model,
            system_prompt=TAX_SYSTEM_PROMPT,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

    async def execute(self, question: ClassifiedQuestion, plan_steps: list[str]) -> str:
        prompt = self._build_prompt(question, plan_steps)
        result = await self._agent.ainvoke({"messages": [{"role": "user", "content": prompt}]})
        return result["messages"][-1]["content"]

    @staticmethod
    def _build_prompt(question: ClassifiedQuestion, plan_steps: list[str]) -> str:
        plan_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(plan_steps))
        return f"""请回答以下税务问题。

问题：{question.text}

意图类别：{question.intent}

执行计划：
{plan_text}

请按照计划逐步回答，最终给出结构化的答案。"""
