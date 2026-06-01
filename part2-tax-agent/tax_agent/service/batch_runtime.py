from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from tax_agent.domain.intent_classifier import ClassifiedQuestion, IntentClassifier
from tax_agent.io.output_formatter import OutputFormatter
from tax_agent.io.question_extractor import extract_questions
from tax_agent.runtime.conversation import ConversationMessage, ConversationRequest, InteractionMode


class BatchRequest(BaseModel):
    session_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    input_file: str = Field(min_length=1)
    thread_strategy: str = "per_question"
    interaction_mode: InteractionMode | None = None


@dataclass
class BatchResponse:
    session_id: str
    trace_id: str
    total_questions: int
    output_paths: dict[str, str]


class BatchProcessor:
    def __init__(self, executor, classifier: IntentClassifier | None = None, formatter: OutputFormatter | None = None):
        self._executor = executor
        self._classifier = classifier or IntentClassifier()
        self._formatter = formatter or OutputFormatter()

    async def run(self, request: BatchRequest, output_dir: str | Path) -> BatchResponse:
        if request.thread_strategy != "per_question":
            raise ValueError("Only thread_strategy='per_question' is supported")

        questions = self._classifier.classify_batch(extract_questions(request.input_file))
        results = []
        for index, question in enumerate(questions, start=1):
            turn_request = self._turn_request(request, question, index)
            execution = await self._executor.execute_turn(turn_request)
            results.append(
                self._formatter.format(
                    question,
                    execution.answer,
                    citations=execution.citations,
                    tool_events=execution.tool_events,
                    domain_analysis=execution.domain_analysis,
                    skills=execution.skills,
                )
            )

        paths = self._formatter.write_all(results, output_dir, run_id=request.trace_id)
        return BatchResponse(
            session_id=request.session_id,
            trace_id=request.trace_id,
            total_questions=len(results),
            output_paths=paths,
        )

    @staticmethod
    def _turn_request(request: BatchRequest, question: ClassifiedQuestion, index: int) -> ConversationRequest:
        return ConversationRequest(
            session_id=request.session_id,
            trace_id=request.trace_id,
            thread_id=f"{request.session_id}-q{index}",
            messages=[ConversationMessage(role="user", content=question.text)],
        )
