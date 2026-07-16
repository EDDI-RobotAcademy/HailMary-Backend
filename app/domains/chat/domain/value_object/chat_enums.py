from enum import Enum


class ChatCharacter(str, Enum):
    """도화선 2.0 채팅 캐릭터 고정 ID — 프로토타입 characterAsset ID와 동일."""

    YEONU = "yeonu"
    DOYOON = "doyoon"
    KKEBI = "kkebi"


class ChatMode(str, Enum):
    """사적(저코인) / 사주(고코인, DL-C02: ON이면 입력 무관 전부 고코인)."""

    CASUAL = "casual"
    SAJU = "saju"
