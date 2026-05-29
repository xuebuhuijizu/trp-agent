from collections.abc import AsyncIterator, Callable
from typing import Any

from agent_executor import AgentExecutor
from batch_runtime import BatchProcessor, BatchRequest
from config import AgentConfig
from conversation import ChatResponse, ConversationRequest
from sse_protocol import render_sse


DEFAULT_API_PORT = 3004


def create_app(executor_factory: Callable[[], AgentExecutor] | None = None):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import StreamingResponse
    except Exception as exc:
        raise RuntimeError("FastAPI service requires fastapi and uvicorn") from exc

    app = FastAPI(title="DeepAgents Tax Runtime", version="0.4.0")
    factory = executor_factory or (lambda: AgentExecutor(AgentConfig()))

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "port": DEFAULT_API_PORT}

    @app.post("/chat")
    async def chat(request: ConversationRequest) -> dict:
        executor = factory()
        result = await executor.execute_turn(request)
        return ChatResponse(
            session_id=request.session_id,
            trace_id=request.trace_id,
            thread_id=request.thread_id,
            answer=result.answer,
            citations=result.citations,
            checkpoint={
                "backend_type": executor.checkpoint_backend_type,
                "thread_id": request.thread_id,
            },
            observability={"provider": executor.observability_provider},
        ).model_dump()

    @app.post("/chat/stream")
    async def chat_stream(request: ConversationRequest):
        executor = factory()

        async def events() -> AsyncIterator[str]:
            yield render_sse(
                "run.started",
                {
                    "session_id": request.session_id,
                    "trace_id": request.trace_id,
                    "thread_id": request.thread_id,
                },
            )
            try:
                result = await executor.execute_turn(request)
            except Exception as exc:
                yield render_sse("run.error", {"error": type(exc).__name__, "message": str(exc)})
                return
            if result.answer:
                yield render_sse("agent.message.delta", {"text": result.answer})
            yield render_sse(
                "run.finished",
                {
                    "answer": result.answer,
                    "citations": result.citations,
                    "thread_id": request.thread_id,
                },
            )

        return StreamingResponse(events(), media_type="text/event-stream")

    @app.post("/batch")
    async def batch(request: BatchRequest) -> dict:
        executor = factory()
        processor = BatchProcessor(executor)
        response = await processor.run(request, output_dir=executor.output_dir)
        return {
            "session_id": response.session_id,
            "trace_id": response.trace_id,
            "total_questions": response.total_questions,
            "output_paths": response.output_paths,
        }

    @app.get("/threads/{thread_id}/state")
    async def get_thread_state(thread_id: str) -> dict:
        executor = factory()
        try:
            return {"thread_id": thread_id, "state": executor.get_state(thread_id)}
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

    @app.get("/threads/{thread_id}/history")
    async def get_thread_history(thread_id: str) -> dict:
        executor = factory()
        try:
            return {"thread_id": thread_id, "history": executor.get_state_history(thread_id)}
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

    return app


app = create_app
