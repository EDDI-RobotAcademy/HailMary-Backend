from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChatStreamEvent:
    """SSE로 내보낼 이벤트 1건 — 계약은 CHAT_SSOT.md "SSE 계약" 절.

    event: start | delta | saju_block(P3) | usage(P4) | done | error
    직렬화(event:/data: 프레임)는 inbound adapter(sse.py) 책임.
    """

    event: str
    data: dict[str, Any] = field(default_factory=dict)
