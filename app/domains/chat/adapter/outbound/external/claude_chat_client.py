import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx
from anthropic import (
    APIConnectionError,
    APIStatusError,
    AsyncAnthropic,
    RateLimitError,
)

from app.domains.chat.domain.port.chat_client_port import ChatClientError
from app.domains.chat.domain.value_object.chat_turn import ChatTurn
from app.infrastructure.external.tls import build_client_ssl_context

logger = logging.getLogger(__name__)


class ClaudeChatClient:
    """캐릭터 챗 전용 Claude 스트리밍 클라이언트 (ChatClientPort 구현).

    ai 도메인 ClaudeClient(버퍼드, 유료 결과지)와 분리 — 도메인 간 에러 타입 결합 방지.
    max_retries=5는 스트림 "시작" 재시도에 적용(529 대비, ai 도메인과 동일 근거).
    스트림 도중 오류는 ChatClientError로 변환되어 usecase가 error 이벤트로 처리.
    """

    def __init__(self, *, api_key: str, model: str) -> None:
        # cadata SSL 컨텍스트: Windows 로컬 OPENSSL_Applink 크래시 우회 (infrastructure/external/tls.py).
        # certifi 동일 신뢰 저장소라 전 환경 동작 불변.
        http_client = httpx.AsyncClient(verify=build_client_ssl_context())
        self._client = AsyncAnthropic(api_key=api_key, max_retries=5, http_client=http_client)
        self._model = model

    async def stream_chat(
        self,
        *,
        system_prompt: str,
        turns: list[ChatTurn],
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        messages = [{"role": t.role, "content": t.content} for t in turns]
        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages,  # type: ignore[arg-type]
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except RateLimitError as exc:
            raise ChatClientError("Claude API rate limit") from exc
        except APIConnectionError as exc:
            raise ChatClientError("Claude API 연결 실패") from exc
        except APIStatusError as exc:
            raise ChatClientError(f"Claude API status error: {exc.status_code}") from exc

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
        # 사주 모드: 강제 tool_choice로 캐릭터별 스키마 dict를 버퍼드 생성 (스트리밍 아님).
        messages = [{"role": t.role, "content": t.content} for t in turns]
        try:
            resp = await self._client.messages.create(  # type: ignore[call-overload]
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
            )
        except RateLimitError as exc:
            raise ChatClientError("Claude API rate limit") from exc
        except APIConnectionError as exc:
            raise ChatClientError("Claude API 연결 실패") from exc
        except APIStatusError as exc:
            raise ChatClientError(f"Claude API status error: {exc.status_code}") from exc

        for block in resp.content:
            if block.type == "tool_use" and block.name == tool_name:
                # block.input 은 스키마 검증된 dict — 방어적 복사
                return dict(block.input)
        raise ChatClientError("사주 블록 tool_use 응답 누락")
