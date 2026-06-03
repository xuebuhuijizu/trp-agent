from tax_agent.agent.context_policy import MEMORY_SOURCES, SKILL_SOURCES, build_filesystem_backend
from tax_agent.agent.instructions import TAX_SYSTEM_PROMPT
from tax_agent.agent.tool_manifest import TAX_AGENT_TOOLS
from tax_agent.business.answers.models import TaxAnswer
from tax_agent.runtime.config import AgentConfig


def build_tax_agent(config: AgentConfig, checkpointer=None):
    from deepagents import create_deep_agent
    from langchain.chat_models import init_chat_model

    model = init_chat_model(
        config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
    return create_deep_agent(
        model=model,
        system_prompt=TAX_SYSTEM_PROMPT,
        tools=TAX_AGENT_TOOLS,
        skills=SKILL_SOURCES,
        memory=MEMORY_SOURCES,
        backend=build_filesystem_backend(),
        response_format=TaxAnswer,
        checkpointer=checkpointer,
    )
