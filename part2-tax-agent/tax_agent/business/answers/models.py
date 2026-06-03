from typing import Any

from pydantic import BaseModel, Field


class TaxCitation(BaseModel):
    citation_id: str | None = Field(default=None, description="引用 ID")
    source_id: str = Field(description="检索来源 ID")
    source_type: str | None = Field(default=None, description="引用来源类型")
    provider_id: str | None = Field(default=None, description="ReferenceProvider ID")
    title: str = Field(description="检索来源标题")
    locator: str | None = Field(default=None, description="来源内定位信息")
    snippet: str | None = Field(default=None, description="引用片段")
    confidence: float | None = Field(default=None, description="检索或匹配置信度")
    retrieved_at: str | None = Field(default=None, description="检索时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="来源特有扩展字段")


class TaxAnswer(BaseModel):
    question: str = Field(description="原始税务问题")
    intent: str = Field(description="业务标签：definition/rate/compliance")
    answer: str = Field(description="面向用户的中文回答")
    citations: list[TaxCitation] = Field(default_factory=list, description="结构化引用来源")
