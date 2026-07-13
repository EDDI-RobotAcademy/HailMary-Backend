import hashlib
from typing import Any

from app.domains.chat.domain.port.saju_cache_port import SajuCachePort
from app.infrastructure.cache.redis_client import RedisCache

_KEY_VERSION = "v1"


def _key(fingerprint: str) -> str:
    # PII 평문(생년월일·성별) 대신 해시만 키에 — kkebi PII 규칙 정합
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return f"chat:saju:{_KEY_VERSION}:{digest}"


class SajuCacheAdapter(SajuCachePort):
    """SajuCachePort 구현 — RedisCache 래핑. 사주는 불변이라 장기 TTL, 장애 시 graceful miss."""

    def __init__(self, cache: RedisCache | None, ttl_seconds: int) -> None:
        self._cache = cache
        self._ttl = ttl_seconds

    async def get(self, fingerprint: str) -> dict[str, Any] | None:
        if self._cache is None:
            return None
        result = await self._cache.get_json(_key(fingerprint))
        return result if isinstance(result, dict) else None

    async def set(self, fingerprint: str, saju_raw: dict[str, Any]) -> None:
        if self._cache is None:
            return
        await self._cache.set_json(_key(fingerprint), saju_raw, self._ttl)
