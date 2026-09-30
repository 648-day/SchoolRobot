"""FastAPI 入口（学生 C 第 1 阶段）。

- create_app 支持注入 Settings / RAGService，便于 TestClient 离线运行。
- import 与 startup 阶段不加载嵌入模型、不访问 Ollama；keyword 模式的知识库也是
  首次检索时才惰性读取。
- GET /health 只报告进程与配置，不声称 Ollama / 向量库可用。
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.chat import router as chat_router
from app.core.config import Settings
from app.services.llm_service import LLMConnectionError, LLMTimeoutError, LLMUpstreamError
from app.services.rag_service import RAGService
from app.services.retriever import RetrieverUnavailable

logger = logging.getLogger(__name__)


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RetrieverUnavailable)
    async def _retriever_unavailable(_request, exc: RetrieverUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(LLMConnectionError)
    async def _llm_connection(_request, exc: LLMConnectionError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(LLMTimeoutError)
    async def _llm_timeout(_request, exc: LLMTimeoutError) -> JSONResponse:
        return JSONResponse(status_code=504, content={"detail": str(exc)})

    @app.exception_handler(LLMUpstreamError)
    async def _llm_upstream(_request, exc: LLMUpstreamError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})


def create_app(settings: Settings | None = None, rag_service: RAGService | None = None) -> FastAPI:
    """构造应用；rag_service 可注入（测试或替换实现）。"""
    settings = settings if settings is not None else Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        service = getattr(app.state, "rag_service", None)
        close = getattr(service, "close", None)
        if callable(close):
            close()

    app = FastAPI(title="Campus AI Assistant API", lifespan=lifespan)
    app.state.settings = settings

    if rag_service is not None:
        app.state.rag_service = rag_service
        app.state.rag_service_error = None
    else:
        try:
            app.state.rag_service = RAGService.from_settings(settings)
            app.state.rag_service_error = None
        except RetrieverUnavailable as exc:
            # 配置问题：/health 仍可用，/chat 明确返回 503，不静默换模式
            logger.warning("RAG 服务初始化失败：%s", exc)
            app.state.rag_service = None
            app.state.rag_service_error = exc

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.include_router(chat_router)
    _register_error_handlers(app)

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"message": "Campus AI Assistant backend is running"}

    @app.get("/health")
    def health() -> dict:
        """只报告进程与配置；不探测 Ollama / 向量库，避免谎报依赖可用。"""
        return {
            "status": "ok",
            "checks": ["process", "config"],
            "external_dependencies_checked": False,
            "retrieval_mode": settings.retrieval_mode,
            "model": settings.model_name,
            "rag_service_ready": app.state.rag_service is not None,
            "note": "仅报告进程与配置，不检测 Ollama 与向量库是否可用",
        }

    return app


app = create_app()
