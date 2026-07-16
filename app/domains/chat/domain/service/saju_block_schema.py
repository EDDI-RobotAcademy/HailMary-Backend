"""사주 모드 구조화 블록 tool 스키마 — 캐릭터별 (프로토타입 SajuBlock 타입 미러).

Claude forced tool_choice로 이 스키마에 맞는 JSON을 강제 생성한다(버퍼드).
프로토타입 domain/model/message.ts의 YeonuSajuBlock/DoyoonSajuBlock/KkebiSajuBlock와 1:1.
strict는 미사용(모델 호환) — 반환 dict는 usecase에서 방어적으로 검증.
"""

from typing import Any

from app.domains.chat.domain.value_object.chat_enums import ChatCharacter

TOOL_NAME = "emit_saju_block"

# 연우: kind=yeonu, scene + evidence[{hanja,element,note}] + advice (한자 음독 병기)
_YEONU_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["yeonu"]},
        "scene": {"type": "string", "description": "운명론적·초자연적 장면 묘사 한 문단"},
        "evidence": {
            "type": "array",
            "description": "사주 근거 2~4개",
            "items": {
                "type": "object",
                "properties": {
                    "hanja": {"type": "string", "description": "한자+음독 병기, 예: 丙火(병화)"},
                    "element": {"type": "string", "description": "오행, 예: 화(火)"},
                    "note": {"type": "string", "description": "이 근거의 해석 한 줄"},
                },
                "required": ["hanja", "element", "note"],
            },
        },
        "advice": {"type": "string", "description": "실전 조언 한 문단"},
    },
    "required": ["kind", "scene", "evidence", "advice"],
}

# 도윤: kind=doyoon, comment + radar[{axis,score}] + percents[{label,value}]
_DOYOON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["doyoon"]},
        "comment": {"type": "string", "description": "분석 코멘트 한 문단(존댓말)"},
        "radar": {
            "type": "array",
            "description": "레이더 축 3~5개",
            "items": {
                "type": "object",
                "properties": {
                    "axis": {"type": "string", "description": "축 이름, 예: 연애"},
                    "score": {"type": "integer", "description": "0~100"},
                },
                "required": ["axis", "score"],
            },
        },
        "percents": {
            "type": "array",
            "description": "퍼센트 지표 2~4개",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "integer", "description": "0~100"},
                },
                "required": ["label", "value"],
            },
        },
    },
    "required": ["kind", "comment", "radar", "percents"],
}

# 깨비: kind=kkebi, summary
_KKEBI_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["kkebi"]},
        "summary": {"type": "string", "description": "가벼운 요약 한두 문장(영물 톤)"},
    },
    "required": ["kind", "summary"],
}

_SCHEMAS: dict[ChatCharacter, dict[str, Any]] = {
    ChatCharacter.YEONU: _YEONU_SCHEMA,
    ChatCharacter.DOYOON: _DOYOON_SCHEMA,
    ChatCharacter.KKEBI: _KKEBI_SCHEMA,
}

_LEAD_KEY: dict[ChatCharacter, str] = {
    ChatCharacter.YEONU: "scene",
    ChatCharacter.DOYOON: "comment",
    ChatCharacter.KKEBI: "summary",
}


def saju_tool(character: ChatCharacter) -> dict[str, Any]:
    """Anthropic tool 정의 — forced tool_choice로 사용."""
    return {
        "name": TOOL_NAME,
        "description": (
            f"{character.value} 캐릭터의 사주 풀이를 구조화된 형식으로 출력한다. "
            "한자는 음독 병기, 캐릭터 언어 분리 규칙 준수."
        ),
        "input_schema": _SCHEMAS[character],
    }


def lead_text(character: ChatCharacter, block: dict[str, Any]) -> str:
    """말풍선 미리보기/저장용 리드 텍스트 (사주 블록에서 추출)."""
    value = block.get(_LEAD_KEY[character], "")
    return value if isinstance(value, str) else ""
