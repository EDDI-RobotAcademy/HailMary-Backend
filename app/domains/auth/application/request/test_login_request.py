from pydantic import BaseModel


class TestLoginRequest(BaseModel):
    """카드사 심사용 테스트 로그인 — OAuth 아닌 ID/PW. 단일 공유 계정."""

    __test__ = False  # pytest가 'Test*'로 오수집하지 않게

    username: str
    password: str
