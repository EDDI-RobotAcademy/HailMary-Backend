from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.domains.chat.domain.value_object.chat_turn import ChatTurn


class ChatClientError(Exception):
    """채팅 LLM 호출 실패 — Adapter에서 SDK 에러를 이 타입으로 변환."""


class ChatClientPort(Protocol):
    """캐릭터 챗 클라이언트 포트.

    실 구현: adapter/outbound/external/claude_chat_client.py.
    - stream_chat: 캐주얼 모드 — 텍스트 델타를 조각 단위로 yield (messages.stream).
    - generate_saju_block: 사주 모드 — 캐릭터별 스키마로 강제 tool-use, 구조화 dict를
      버퍼드로 1회 반환 (messages.create + tool_choice). 도윤 radar/percents는 부분
      스트림이 무의미하므로 통짜 생성이 설계 계약 (CHAT_SSOT SSE 계약).
    """

    def stream_chat(
        self,
        *,
        system_prompt: str,
        turns: list[ChatTurn],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]: ...

    async def generate_saju_block(
        self,
        *,
        system_prompt: str,
        turns: list[ChatTurn],
        tool: dict[str, Any],
        tool_name: str,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        """강제 tool_choice로 tool의 input_schema에 맞는 dict를 생성해 반환."""
        ...
