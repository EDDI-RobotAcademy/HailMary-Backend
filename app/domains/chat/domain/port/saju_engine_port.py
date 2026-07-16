from typing import Any, Protocol


class SajuEnginePort(Protocol):
    """사주 계산 엔진 — FortuneTeller. main.py에서 기존 FortuneTellerAdapter로 와이어링.

    호출은 프로필 캡처 시 1회(캐시 미스 시). 팀 룰 "플로당 1회"와 정합.
    """

    async def analyze(self, saju_data: dict[str, Any]) -> dict[str, Any]: ...
