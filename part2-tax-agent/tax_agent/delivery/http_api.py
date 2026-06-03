from collections.abc import AsyncIterator, Awaitable, Callable
import inspect
import json
from typing import Any

from tax_agent.delivery.batch import BatchProcessor, BatchRequest
from tax_agent.runtime.config import AgentConfig
from tax_agent.runtime.conversation import ChatResponse, ConversationRequest
from tax_agent.runtime.executor import AgentExecutor, ModelOutputError
from tax_agent.runtime.sse import render_sse


DEFAULT_API_PORT = 3004


ExecutorFactory = Callable[[], AgentExecutor | Awaitable[AgentExecutor]]


async def _resolve_executor(factory: ExecutorFactory) -> AgentExecutor:
    executor = factory()
    if inspect.isawaitable(executor):
        return await executor
    return executor


def utf8_json(payload: Any, status_code: int = 200):
    from fastapi import Response

    return Response(
        content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        media_type="application/json; charset=utf-8",
    )


def create_app(executor_factory: ExecutorFactory | None = None):
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import StreamingResponse
    except Exception as exc:
        raise RuntimeError("FastAPI service requires fastapi and uvicorn") from exc

    app = FastAPI(title="DeepAgents Tax Runtime", version="0.4.0")
    factory: ExecutorFactory = executor_factory or (lambda: AgentExecutor.create(AgentConfig()))

    @app.get("/health")
    async def health():
        return utf8_json({"status": "ok", "port": DEFAULT_API_PORT})

    @app.post("/chat")
    async def chat(request: ConversationRequest):
        executor = await _resolve_executor(factory)
        try:
            result = await executor.execute_turn(request)
        except ModelOutputError as exc:
            return utf8_json(
                {
                    "error": "ModelOutputError",
                    "message": str(exc),
                    "session_id": request.session_id,
                    "trace_id": request.trace_id,
                    "thread_id": request.thread_id,
                },
                status_code=502,
            )
        response = ChatResponse(
            session_id=request.session_id,
            trace_id=request.trace_id,
            thread_id=request.thread_id,
            answer=result.answer,
            citations=result.citations,
            artifact=getattr(result, "artifact", None),
            checkpoint={
                "backend_type": executor.checkpoint_backend_type,
                "thread_id": request.thread_id,
            },
            observability={"provider": executor.observability_provider},
        )
        return utf8_json(response.model_dump(exclude_none=True))

    @app.post("/chat/stream")
    async def chat_stream(request: ConversationRequest):
        executor = await _resolve_executor(factory)

        async def events() -> AsyncIterator[str]:
            try:
                async for event in executor.stream_turn(request):
                    yield render_sse(event["event"], event["data"])
            except Exception as exc:
                yield render_sse("RUN_ERROR", {"error": type(exc).__name__, "message": str(exc)})

        return StreamingResponse(events(), media_type="text/event-stream; charset=utf-8")

    @app.post("/batch")
    async def batch(request: BatchRequest):
        executor = await _resolve_executor(factory)
        processor = BatchProcessor(executor)
        try:
            response = await processor.run(request, output_dir=executor.output_dir)
        except ModelOutputError as exc:
            return utf8_json({"error": "ModelOutputError", "message": str(exc)}, status_code=502)
        return utf8_json(
            {
                "session_id": response.session_id,
                "trace_id": response.trace_id,
                "total_questions": response.total_questions,
                "output_paths": response.output_paths,
            }
        )

    @app.get("/threads/{thread_id}/state")
    async def get_thread_state(thread_id: str):
        executor = await _resolve_executor(factory)
        try:
            return utf8_json({"thread_id": thread_id, "state": executor.get_state(thread_id)})
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

    @app.get("/threads/{thread_id}/history")
    async def get_thread_history(thread_id: str):
        executor = await _resolve_executor(factory)
        try:
            return utf8_json({"thread_id": thread_id, "history": executor.get_state_history(thread_id)})
        except NotImplementedError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

    return app
