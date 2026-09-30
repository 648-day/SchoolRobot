"""聊天接口请求 / 响应类型（学生 C 第 1 阶段）。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_CHARS = 2000


class ChatRequest(BaseModel):
    """POST /chat 请求体。message 先 trim，再要求 1..2000 个字符。"""

    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_CHARS)

    @field_validator("message", mode="before")
    @classmethod
    def _strip_message(cls, value: object) -> object:
        # 只对字符串做 trim；其它类型交给 pydantic 判为 422
        if isinstance(value, str):
            return value.strip()
        return value


class SourceItem(BaseModel):
    """一条本次实际引用进上下文的资料来源。"""

    index: int = Field(..., ge=1, description="引用编号，与答案里的 [编号] 一致")
    title: str = Field(..., description="文档标题")
    source: str = Field(..., description="仓库相对路径（不含盘符）")
    snippet: str = Field(..., description="实际放入提示词的片段")
    score: float = Field(..., description="检索分数（keyword 为启发式相关度，chroma 为距离换算分）")


class ChatResponse(BaseModel):
    """POST /chat 响应体；answer 保持前端兼容字段。"""

    answer: str
    sources: list[SourceItem] = Field(default_factory=list)
    retrieval_mode: str = Field(..., description="本次检索模式：keyword 或 chroma")
