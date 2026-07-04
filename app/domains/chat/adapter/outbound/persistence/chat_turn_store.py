from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chat.domain.entity.chat_message import ChatMessage
from app.domains.chat.domain.port.chat_turn_store_port import TurnBegin
from app.domains.chat.domain.port.conversation_repository_port import (
    ConversationNotFoundError,
)
from app.domains.chat.domain.value_object.chat_enums import ChatCharacter, ChatMode
from app.domains.chat.infrastructure.mapper.chat_mapper import ChatMessageMapper
from app.domains.chat.infrastructure.orm.chat_message_orm import ChatMessageORM
from app.domains.chat.infrastructure.orm.conversation_orm import ConversationORM


class ChatTurnStore:
    """스트리밍 턴 영속화 (ChatTurnStorePort 구현) — 단명 자체 세션.

    요청 세션(`_get_session`, 요청당 단일 트랜잭션)을 스트림 수명 동안 잡지 않기 위해
    각 메서드가 session_factory로 자체 세션을 열고 원자 커밋한다
    (main.py `_compose_report_background` 패턴, CHAT_SSOT.md SSE 계약 §코인 선차감-환불).
    """

    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory

    async def begin_turn(
        self,
        *,
        conversation_id: int,
        account_id: int,
        content: str,
        mode: ChatMode,
        history_window: int,
    ) -> TurnBegin:
        async with self._session_factory() as session, session.begin():
            conv = (
                await session.execute(
                    select(ConversationORM).where(
                        ConversationORM.id == conversation_id,
                        ConversationORM.account_id == account_id,
                    )
                )
            ).scalar_one_or_none()
            if conv is None:
                raise ConversationNotFoundError(f"conversation {conversation_id} not found")

            # 직전 이력 (user 메시지 INSERT 전 스냅샷, 최신 N → 오름차순)
            rows = (
                (
                    await session.execute(
                        select(ChatMessageORM)
                        .where(ChatMessageORM.conversation_id == conversation_id)
                        .order_by(ChatMessageORM.id.desc())
                        .limit(history_window)
                    )
                )
                .scalars()
                .all()
            )
            history: list[ChatMessage] = [ChatMessageMapper.to_entity(r) for r in reversed(rows)]

            user_orm = ChatMessageORM(
                conversation_id=conversation_id,
                role="user",
                msg_type="text",
                mode=mode.value,
                content=content,
            )
            session.add(user_orm)
            conv.last_message_at = datetime.now()
            await session.flush()
            return TurnBegin(
                character=ChatCharacter(conv.character_id),
                user_message_id=user_orm.id,
                history=history,
            )

    async def complete_turn(
        self,
        *,
        conversation_id: int,
        content: str,
        mode: ChatMode,
    ) -> int:
        async with self._session_factory() as session, session.begin():
            orm = ChatMessageORM(
                conversation_id=conversation_id,
                role="character",
                msg_type="text",
                mode=mode.value,
                content=content,
            )
            session.add(orm)
            conv = (
                await session.execute(
                    select(ConversationORM).where(ConversationORM.id == conversation_id)
                )
            ).scalar_one_or_none()
            if conv is not None:
                conv.last_message_at = datetime.now()
            await session.flush()
            return orm.id
