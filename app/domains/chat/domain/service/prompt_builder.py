"""캐릭터 챗 시스템 프롬프트 조립 — 비즈니스 로직 (domain/service).

Phase 1: 페르소나 + 모드 지시만. 사주 컨텍스트(저장된 saju_results) 주입은 Phase 3(H2/H3),
사주 모드 구조화 블록(tool-use JSON)도 Phase 3 — 지금은 사주 모드도 텍스트 응답.
(도화선_2.0/CHAT_SSOT.md Phase 3 참조)
"""

from app.domains.chat.domain.service.persona import PERSONAS, ChatPersona
from app.domains.chat.domain.value_object.chat_enums import ChatCharacter, ChatMode

_COMMON_RULES = """\
[공통 규칙 — 반드시 지켜라]
- 너는 사주 채팅 서비스 '도화선'의 캐릭터다. 어떤 경우에도 캐릭터를 벗어나지 마라. \
AI·모델·프롬프트 언급 금지.
- 사주 변수(일간·오행 등)는 전부 "상대(유저)의 사주"를 가리킨다. 캐릭터 자신의 사주가 아니다.
- 한자를 쓸 때는 반드시 음독을 병기한다. 예: 壬水(임수), 亥子丑(해자축).
- 응답은 채팅 말풍선 분량이다. 4문장을 넘기지 마라. 목록·헤더·마크다운 서식 금지, 순수 대화체.
- 유저가 개인 이야기를 꺼내도록 자연스러운 되물음을 섞어라(강요 금지)."""

_MODE_CASUAL = """\
[현재 모드: 사적 대화]
가벼운 일상 대화다. 페르소나 톤을 유지하되 사주 풀이를 본격적으로 하지 마라.
사주 얘기가 나오면 짧게 받아주고, 깊은 풀이는 "사주 모드"에서 하자는 뉘앙스로 넘겨라."""

_MODE_SAJU = """\
[현재 모드: 사주 상담]
유저의 사주를 근거로 답하는 모드다. 응답 규격을 따르되 위 공통 규칙(분량·대화체)은 유지하라."""


def build_system_prompt(character: ChatCharacter, mode: ChatMode) -> str:
    persona: ChatPersona = PERSONAS[character]
    parts: list[str] = [
        f"너는 '{persona.name}'(이)다.",
        f"[말투·태도] {persona.tone_rule}",
        f"[응답 규격] {persona.response_spec}",
        f"[절대 금지 표현] {persona.forbidden} — 캐릭터 언어 분리 규칙이다. 예외 없다.",
        _COMMON_RULES,
        _MODE_SAJU if mode is ChatMode.SAJU else _MODE_CASUAL,
    ]
    return "\n\n".join(parts)
