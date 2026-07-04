import json
from typing import Any


def format_sse(event: str, data: dict[str, Any]) -> str:
    """SSE 프레임 직렬화 — 계약: CHAT_SSOT.md "SSE 계약" 절.

    data는 단일 JSON 라인(ensure_ascii=False, 한글 원문 유지).
    """
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {payload}\n\n"
