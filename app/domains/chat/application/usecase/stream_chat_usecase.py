import logging
import uuid
from collections.abc import AsyncIterator

from app.domains.chat.application.request.send_chat_message_request import (
    SendChatMessageRequest,
)
from app.domains.chat.application.response.chat_stream_event import ChatStreamEvent
from app.domains.chat.domain.port.chat_client_port import ChatClientError, ChatClientPort
from app.domains.chat.domain.service.prompt_builder import build_system_prompt
from app.domains.chat.domain.value_object.chat_turn import ChatTurn

logger = logging.getLogger(__name__)


def _normalize_turns(history: list[tuple[str, str]], user_message: str) -> list[ChatTurn]:
    """이력 (role, content) 쌍 → Anthropic 턴(user|assistant) 정규화. 공용 (P1 무상태·P2 방 기준).

    - character → assistant 매핑
    - 선두 assistant 턴 제거 (Anthropic은 user 시작 요구 — greet 시드가 선두에 옴)
    - 연속 동일 role은 병합 (교대 규칙 위반 방지)
    """
    turns: list[ChatTurn] = []
    for role_raw, content in history:
        role = "assistant" if role_raw == "character" else "user"
        if not turns and role == "assistant":
            continue
        if turns and turns[-1].role == role:
            turns[-1] = ChatTurn(role=role, content=f"{turns[-1].content}\n{content}")
        else:
            turns.append(ChatTurn(role=role, content=content))
    if turns and turns[-1].role == "user":
        turns[-1] = ChatTurn(role="user", content=f"{turns[-1].content}\n{user_message}")
    else:
        turns.append(ChatTurn(role="user", content=user_message))
    return turns


class StreamChatUseCase:
    """캐릭터 챗 1턴 스트리밍 — Phase 1 무상태 버전.

    Phase 2에서 영속화(방/메시지 저장), Phase 4에서 코인 선차감이 앞뒤로 붙는다.
    이벤트 시퀀스 계약: start → delta* → done | (start → delta* →) error
    """

    def __init__(
        self,
        *,
        chat_client: ChatClientPort,
        max_tokens: int,
        history_window: int,
        temperature: float,
    ) -> None:
        self._chat_client = chat_client
        self._max_tokens = max_tokens
        self._history_window = history_window
        self._temperature = temperature

    async def execute(
        self, request: SendChatMessageRequest, account_id: int | None
    ) -> AsyncIterator[ChatStreamEvent]:
        message_id = uuid.uuid4().hex
        system_prompt = build_system_prompt(request.character_id, request.mode)
        recent = request.history[-self._history_window :]
        turns = _normalize_turns([(m.role, m.content) for m in recent], request.content)

        yield ChatStreamEvent(
            event="start",
            data={"message_id": message_id, "character_id": request.character_id.value},
        )
        streamed = False
        try:
            async for text in self._chat_client.stream_chat(
                system_prompt=system_prompt,
                turns=turns,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            ):
                streamed = True
                yield ChatStreamEvent(event="delta", data={"text": text})
        except ChatClientError as exc:
            logger.warning("chat 스트림 실패 (streamed=%s): %s", streamed, exc)
            yield ChatStreamEvent(
                event="error",
                data={"code": "UPSTREAM_ERROR", "message": "응답 생성에 실패했어요. 다시 시도해 주세요."},
            )
            return
        yield ChatStreamEvent(event="done", data={"stop_reason": "end_turn"})
