from typing import Any

import httpx


class FortuneTellerError(Exception):
    pass


class FortuneTellerClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(f"{self._base_url}/api/saju/free", json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise FortuneTellerError(f"FortuneTeller 오류 {e.response.status_code}") from e
            except httpx.RequestError as e:
                raise FortuneTellerError(f"FortuneTeller 연결 실패: {e}") from e
            return dict(resp.json())
