from dataclasses import dataclass


@dataclass(frozen=True)
class ChatTurn:
    """LLM에 전달하는 대화 턴. role은 Anthropic 규격("user" | "assistant")."""

    role: str
    content: str
