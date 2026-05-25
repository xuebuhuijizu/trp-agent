from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentConfig:
    model: str = "ollama:llama3.1"
    input_file: str = "input.docx"
    output_dir: str = "output"
    temperature: float = 0.1
    max_tokens: int = 4096
    deepagents_tracing: bool = False

    # RAG 装饰器配置（预留）
    rag_enabled: bool = False
    rag_endpoint: Optional[str] = None
    rag_api_key: Optional[str] = None
