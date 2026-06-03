from typing import Literal

from pydantic import BaseModel, Field


MessageRole = Literal["system", "user", "assistant", "tool"]


class ConversationMessage(BaseModel):
    role: MessageRole
    content: str
    name: str | None = None

    def to_agent_message(self) -> dict:
        message = {"role": self.role, "content": self.content}
        if self.name:
            message["name"] = self.name
        return message


class ConversationRequest(BaseModel):
    session_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    messages: list[ConversationMessage] = Field(min_length=1)

    def to_agent_messages(self) -> list[dict]:
        return [message.to_agent_message() for message in self.messages]

    @property
    def current_user_text(self) -> str:
        for message in reversed(self.messages):
            if message.role == "user":
                return message.content
        return self.messages[-1].content


class ChatResponse(BaseModel):
    session_id: str
    trace_id: str
    thread_id: str
    answer: str
    citations: list[dict] = Field(default_factory=list)
    artifact: dict | None = None
    checkpoint: dict = Field(default_factory=dict)
    observability: dict = Field(default_factory=dict)
