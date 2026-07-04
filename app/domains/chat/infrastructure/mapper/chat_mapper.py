from app.domains.chat.domain.entity.chat_message import ChatMessage
from app.domains.chat.domain.entity.conversation import Conversation
from app.domains.chat.domain.value_object.chat_enums import ChatCharacter, ChatMode
from app.domains.chat.infrastructure.orm.chat_message_orm import ChatMessageORM
from app.domains.chat.infrastructure.orm.conversation_orm import ConversationORM


class ConversationMapper:
    @staticmethod
    def to_entity(orm: ConversationORM) -> Conversation:
        return Conversation(
            id=orm.id,
            account_id=orm.account_id,
            character=ChatCharacter(orm.character_id),
            last_message_at=orm.last_message_at,
            created_at=orm.created_at,
        )

    @staticmethod
    def to_orm(entity: Conversation) -> ConversationORM:
        return ConversationORM(
            account_id=entity.account_id,
            character_id=entity.character.value,
            last_message_at=entity.last_message_at,
        )


class ChatMessageMapper:
    @staticmethod
    def to_entity(orm: ChatMessageORM) -> ChatMessage:
        return ChatMessage(
            id=orm.id,
            conversation_id=orm.conversation_id,
            role=orm.role,
            msg_type=orm.msg_type,
            mode=ChatMode(orm.mode),
            content=orm.content,
            saju_block=orm.saju_block,
            input_tokens=orm.input_tokens,
            output_tokens=orm.output_tokens,
            created_at=orm.created_at,
        )

    @staticmethod
    def to_orm(entity: ChatMessage) -> ChatMessageORM:
        return ChatMessageORM(
            conversation_id=entity.conversation_id,
            role=entity.role,
            msg_type=entity.msg_type,
            mode=entity.mode.value,
            content=entity.content,
            saju_block=entity.saju_block,
            input_tokens=entity.input_tokens,
            output_tokens=entity.output_tokens,
        )
