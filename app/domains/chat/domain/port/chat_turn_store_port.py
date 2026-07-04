from dataclasses import dataclass
from typing import Protocol

from app.domains.chat.domain.entity.chat_message import ChatMessage
from app.domains.chat.domain.value_object.chat_enums import ChatCharacter, ChatMode


@dataclass(frozen=True)
class TurnBegin:
    """스트리밍 시작 전 준비 결과 — user 메시지 저장 완료 + 컨텍스트."""

    character: ChatCharacter
    user_message_id: int
    history: list[ChatMessage]  # user 메시지 직전까지, 오래된 순


class ChatTurnStorePort(Protocol):
    """스트리밍 턴 영속화 — **요청 세션을 쓰지 않는다** (단명 자체 세션, 각 메서드가 원자 커밋).

    이유: StreamingResponse 수명 동안 요청 트랜잭션(session.begin())을 잡으면 안 됨.
    main.py `_compose_report_background` 자체 세션 패턴과 동일 근거 (CHAT_SSOT.md SSE 계약).
    """

    async def begin_turn(
        self,
        *,
        conversation_id: int,
        account_id: int,
        content: str,
        mode: ChatMode,
        history_window: int,
    ) -> TurnBegin:
        """소유 검증 → user 메시지 INSERT → 직전 이력 반환. 소유 아님 → ConversationNotFoundError."""
        ...

    async def complete_turn(
        self,
        *,
        conversation_id: int,
        content: str,
        mode: ChatMode,
    ) -> int:
        """캐릭터 메시지 INSERT + 방 last_message_at 갱신. returns message id."""
        ...
