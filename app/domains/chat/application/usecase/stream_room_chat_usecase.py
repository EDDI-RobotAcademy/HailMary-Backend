import logging
from collections.abc import AsyncIterator

from app.domains.chat.application.request.room_requests import SendRoomMessageRequest
from app.domains.chat.application.response.chat_stream_event import ChatStreamEvent
from app.domains.chat.application.usecase.stream_chat_usecase import _normalize_turns
from app.domains.chat.domain.port.chat_client_port import ChatClientError, ChatClientPort
from app.domains.chat.domain.port.chat_turn_store_port import ChatTurnStorePort, TurnBegin
from app.domains.chat.domain.service.prompt_builder import build_system_prompt
from app.domains.chat.domain.service.stream_splitter import split_inner_thought

logger = logging.getLogger(__name__)


class StreamRoomChatUseCase:
    """방 기준 채팅 1턴 스트리밍 + 영속화 (Phase 2).

    2단 구조 (라우터 계약):
      1) begin()  — 스트림 시작 전. 소유 검증 + user 메시지 저장.
         실패는 예외로 → 라우터가 일반 상태코드(404 등) 반환. (Phase 4에서 코인 선차감이 여기 붙음)
      2) stream() — SSE 이벤트 제너레이터. 성공 종료 시 캐릭터 메시지 영속화.
         에러 시 캐릭터 메시지 저장 없음 (부분 응답 정책 = TBD-D, Phase 4에서 재검토).
    """

    def __init__(
        self,
        *,
        chat_client: ChatClientPort,
        turn_store: ChatTurnStorePort,
        max_tokens: int,
        history_window: int,
        temperature: float,
    ) -> None:
        self._chat_client = chat_client
        self._turn_store = turn_store
        self._max_tokens = max_tokens
        self._history_window = history_window
        self._temperature = temperature

    async def begin(
        self, *, room_id: int, account_id: int, request: SendRoomMessageRequest
    ) -> TurnBegin:
        return await self._turn_store.begin_turn(
            conversation_id=room_id,
            account_id=account_id,
            content=request.content,
            mode=request.mode,
            history_window=self._history_window,
        )

    async def stream(
        self, *, room_id: int, begin: TurnBegin, request: SendRoomMessageRequest
    ) -> AsyncIterator[ChatStreamEvent]:
        system_prompt = build_system_prompt(begin.character, request.mode)
        turns = _normalize_turns(
            [(m.role, m.content) for m in begin.history], request.content
        )

        yield ChatStreamEvent(
            event="start",
            data={
                "room_id": room_id,
                "user_message_id": begin.user_message_id,
                "character_id": begin.character.value,
            },
        )
        acc = ""
        inner_thought: str | None = None
        try:
            stream = self._chat_client.stream_chat(
                system_prompt=system_prompt,
                turns=turns,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            )
            # 발화(delta)와 속마음(💭:) 분리. 속마음은 emit-only — 영속화는 mig 014에서 (CHAT_SSOT P3-pre)
            async for kind, text in split_inner_thought(stream):
                if kind == "delta":
                    acc += text
                    yield ChatStreamEvent(event="delta", data={"text": text})
                else:
                    inner_thought = text
        except ChatClientError as exc:
            logger.warning("room chat 스트림 실패 (room=%d, acc=%d자): %s", room_id, len(acc), exc)
            yield ChatStreamEvent(
                event="error",
                data={"code": "UPSTREAM_ERROR", "message": "응답 생성에 실패했어요. 다시 시도해 주세요."},
            )
            return

        if inner_thought:
            yield ChatStreamEvent(event="inner_thought", data={"text": inner_thought})
        message_id = await self._turn_store.complete_turn(
            conversation_id=room_id, content=acc.strip(), mode=request.mode
        )
        yield ChatStreamEvent(
            event="done", data={"stop_reason": "end_turn", "message_id": message_id}
        )
