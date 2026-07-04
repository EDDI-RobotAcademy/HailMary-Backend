from collections.abc import AsyncIterator
from typing import Protocol

from app.domains.chat.domain.value_object.chat_turn import ChatTurn


class ChatClientError(Exception):
    """채팅 LLM 호출 실패 — Adapter에서 SDK 에러를 이 타입으로 변환."""


class ChatClientPort(Protocol):
    """캐릭터 챗 스트리밍 클라이언트 포트.

    실 구현: adapter/outbound/external/claude_chat_client.py (messages.stream).
    구현체는 async generator — 텍스트 델타를 조각 단위로 yield 한다.
    """

    def stream_chat(
        self,
        *,
        system_prompt: str,
        turns: list[ChatTurn],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]: ...
