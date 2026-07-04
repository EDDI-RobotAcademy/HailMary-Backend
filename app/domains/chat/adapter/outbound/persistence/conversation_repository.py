from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.chat.domain.entity.chat_message import ChatMessage
from app.domains.chat.domain.entity.conversation import Conversation
from app.domains.chat.domain.port.conversation_repository_port import (
    ConversationNotFoundError,
    ConversationRepositoryPort,
    RoomSummary,
)
from app.domains.chat.domain.value_object.chat_enums import ChatCharacter, ChatMode
from app.domains.chat.infrastructure.mapper.chat_mapper import (
    ChatMessageMapper,
    ConversationMapper,
)
from app.domains.chat.infrastructure.orm.chat_message_orm import ChatMessageORM
from app.domains.chat.infrastructure.orm.conversation_orm import ConversationORM


class ConversationRepository(ConversationRepositoryPort):
    """대화방/메시지 CRUD — 요청 세션 기반 (main.py `_get_session` 트랜잭션 안)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_rooms(self, *, account_id: int) -> list[RoomSummary]:
        convs = (
            (
                await self._session.execute(
                    select(ConversationORM)
                    .where(ConversationORM.account_id == account_id)
                    .order_by(ConversationORM.last_message_at.desc())
                )
            )
            .scalars()
            .all()
        )
        summaries: list[RoomSummary] = []
        for conv in convs:
            last = (
                await self._session.execute(
                    select(ChatMessageORM.content)
                    .where(ChatMessageORM.conversation_id == conv.id)
                    .order_by(ChatMessageORM.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            summaries.append(
                RoomSummary(
                    conversation_id=conv.id,
                    character=ChatCharacter(conv.character_id),
                    last_message=last or "",
                    last_message_at=conv.last_message_at,
                )
            )
        return summaries

    async def get_or_create(
        self, *, account_id: int, character: ChatCharacter, greeting: str
    ) -> tuple[Conversation, bool]:
        existing = (
            await self._session.execute(
                select(ConversationORM).where(
                    ConversationORM.account_id == account_id,
                    ConversationORM.character_id == character.value,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return ConversationMapper.to_entity(existing), False

        orm = ConversationORM(account_id=account_id, character_id=character.value)
        self._session.add(orm)
        await self._session.flush()  # id 확보
        # 방 생성 시 페르소나 고정 인사 시드 (LLM 호출 0 — CHAT_SSOT.md Phase 2)
        self._session.add(
            ChatMessageORM(
                conversation_id=orm.id,
                role="character",
                msg_type="text",
                mode=ChatMode.CASUAL.value,
                content=greeting,
            )
        )
        await self._session.flush()
        return ConversationMapper.to_entity(orm), True

    async def get_owned(self, *, conversation_id: int, account_id: int) -> Conversation:
        orm = (
            await self._session.execute(
                select(ConversationORM).where(
                    ConversationORM.id == conversation_id,
                    ConversationORM.account_id == account_id,
                )
            )
        ).scalar_one_or_none()
        if orm is None:
            raise ConversationNotFoundError(f"conversation {conversation_id} not found")
        return ConversationMapper.to_entity(orm)

    async def list_messages(
        self, *, conversation_id: int, before_id: int | None, limit: int
    ) -> list[ChatMessage]:
        stmt = select(ChatMessageORM).where(ChatMessageORM.conversation_id == conversation_id)
        if before_id is not None:
            stmt = stmt.where(ChatMessageORM.id < before_id)
        rows = (
            (await self._session.execute(stmt.order_by(ChatMessageORM.id.desc()).limit(limit)))
            .scalars()
            .all()
        )
        return [ChatMessageMapper.to_entity(r) for r in reversed(rows)]
