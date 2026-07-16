from typing import Any, Protocol


class SajuCachePort(Protocol):
    """FortuneTeller 결과 캐시 — 입력 지문 정확 일치 시 재호출 스킵.

    구현은 RedisCache 래핑(graceful degradation: 미스/장애 시 None). PII 평문은
    키·값에 넣지 않는다 — 키는 지문 해시, 값은 saju_raw(비식별 pillars/wuxing).
    """

    async def get(self, fingerprint: str) -> dict[str, Any] | None: ...

    async def set(self, fingerprint: str, saju_raw: dict[str, Any]) -> None: ...
