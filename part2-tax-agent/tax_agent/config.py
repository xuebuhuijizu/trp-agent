from dataclasses import dataclass, field
import os
from typing import Optional


@dataclass
class AgentConfig:
    model: str = "openai:gpt-4o"
    input_file: str = "input.docx"
    output_dir: str = "output"
    temperature: float = 0.1
    max_tokens: int = 4096
    deepagents_tracing: bool = False
    checkpoint_backend: str = field(default_factory=lambda: os.getenv("CHECKPOINT_BACKEND", "auto"))
    opengauss_dsn: str | None = field(default_factory=lambda: os.getenv("OPENGAUSS_DSN"))
    langfuse_enabled: bool = field(default_factory=lambda: os.getenv("LANGFUSE_ENABLED", "0") == "1")
    service_port: int = field(default_factory=lambda: int(os.getenv("TAX_AGENT_SERVICE_PORT", "3004")))

    # RAG 装饰器配置（预留）
    rag_enabled: bool = False
    rag_endpoint: Optional[str] = None
    rag_api_key: Optional[str] = None
