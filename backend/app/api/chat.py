"""聊天接口（学生 C 第 1 阶段）。

- POST /chat：非流式 RAG 问答。前端会先请求 /chat_with_memory，任何请求失败
  （当前该接口尚未实现，返回 404）都会回落到这里。
- 不实现 /chat_with_memory（A 同学负责），不写历史记录。
- 同步路由函数由 FastAPI 放进线程池执行，不阻塞事件循环。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.rag_service import RAGService
from app.services.retriever import RetrieverUnavailable

router = APIRouter(tags=["chat"])


def get_rag_service(request: Request) -> RAGService:
    """从 app.state 取 RAGService（create_app 注入，测试可覆盖依赖）。"""
    service = getattr(request.app.state, "rag_service", None)
    if service is None:
        error = getattr(request.app.state, "rag_service_error", None)
        raise error or RetrieverUnavailable("RAG 服务未初始化，请检查后端配置")
    return service


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, service: RAGService = Depends(get_rag_service)) -> ChatResponse:
    """基础问答：检索 + 大模型，一次返回完整答案。"""
    result = service.answer(payload.message)
    return ChatResponse(
        answer=result.answer,
        sources=result.sources,
        retrieval_mode=result.retrieval_mode,
    )
