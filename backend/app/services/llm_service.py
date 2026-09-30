"""Ollama 大模型调用（非流式）。

官方接口文档：https://docs.ollama.com/api/chat
- POST /api/chat，messages + stream=false，temperature=0.1
- think 默认 false（适配本地 qwen3.5:4b），只读取 message.content，不返回 thinking
- 连接失败 / 超时 / 模型缺失 / 无效响应分别抛出可安全返回的业务异常
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """模型调用错误基类；str(exc) 可以安全返回给客户端。"""


class LLMConnectionError(LLMError):
    """连接不上 Ollama（接口层映射 503）。"""


class LLMTimeoutError(LLMError):
    """调用 Ollama 超时（接口层映射 504）。"""


class LLMUpstreamError(LLMError):
    """Ollama 返回错误状态或无效响应（接口层映射 502）。"""


class OllamaLLM:
    """Ollama /api/chat 非流式封装。"""

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3.5:4b",
        timeout_seconds: float = 15.0,
        think: bool = False,
        temperature: float = 0.1,
        client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.think = think
        self.temperature = temperature
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            transport=transport,
        )
        self._closed = False

    def close(self) -> None:
        """关闭自建的 HTTP 客户端；外部注入的 client 由调用方负责关闭。"""
        if self._owns_client and not self._closed:
            self._client.close()
            self._closed = True

    def chat(self, messages: list[dict[str, str]]) -> str:
        """调用 /api/chat，返回 message.content 文本。"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "options": {"temperature": self.temperature},
        }
        try:
            response = self._client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("大模型响应超时，请稍后重试") from exc
        except httpx.TransportError as exc:
            raise LLMConnectionError("无法连接本地 Ollama 服务，请确认 Ollama 已启动") from exc

        if response.status_code == 404:
            logger.warning("Ollama 返回 404：模型 %s 可能未安装", self.model)
            raise LLMUpstreamError(f"Ollama 未找到模型 {self.model}，请先执行 ollama pull {self.model}")
        if response.status_code >= 400:
            logger.warning("Ollama 返回 HTTP %s", response.status_code)
            raise LLMUpstreamError("Ollama 服务返回错误状态，请检查模型与 Ollama 日志")

        try:
            data = response.json()
        except ValueError as exc:
            logger.warning("Ollama 响应不是合法 JSON")
            raise LLMUpstreamError("大模型返回内容无法解析") from exc

        if not isinstance(data, dict):
            raise LLMUpstreamError("大模型返回内容格式不正确")
        message = data.get("message")
        if not isinstance(message, dict):
            raise LLMUpstreamError("大模型返回内容格式不正确")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMUpstreamError("大模型返回内容为空")
        return content.strip()
