import asyncio
import logging
from collections.abc import AsyncGenerator, Coroutine
from datetime import datetime
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.ai.adapter.inbound.api.paid_report_router import (
    get_paid_report_usecase,
)
from app.domains.ai.adapter.inbound.api.paid_report_router import (
    router as paid_report_router,
)
from app.domains.ai.adapter.inbound.api.paid_report_router import (
    share_router as paid_report_share_router,
)
from app.domains.ai.adapter.outbound.external.claude_client import ClaudeClient
from app.domains.ai.adapter.outbound.persistence.paid_report_repository import (
    PaidReportRepository,
)
from app.domains.ai.application.usecase.compose_paid_report_usecase import (
    ComposePaidReportUseCase,
)
from app.domains.ai.application.usecase.create_paid_report_usecase import (
    CreatePaidReportUseCase,
)
from app.domains.ai.application.usecase.determine_doyoon_name_address_usecase import (
    DetermineDoyoonNameAddressUseCase,
)
from app.domains.ai.application.usecase.generate_p0_diagnosis_usecase import (
    GenerateP0DiagnosisUseCase,
)
from app.domains.ai.application.usecase.generate_p1_emotion_usecase import (
    GenerateP1EmotionUseCase,
)
from app.domains.ai.application.usecase.generate_p1_opening_usecase import (
    GenerateP1OpeningUseCase,
)
from app.domains.ai.application.usecase.generate_p1_trigger_usecase import (
    GenerateP1TriggerUseCase,
)
from app.domains.ai.application.usecase.generate_p2_hurt_usecase import (
    GenerateP2HurtUseCase,
)
from app.domains.ai.application.usecase.generate_p2_recovery_usecase import (
    GenerateP2RecoveryUseCase,
)
from app.domains.ai.application.usecase.generate_p3_blockade_usecase import (
    GenerateP3BlockadeUseCase,
)
from app.domains.ai.application.usecase.generate_p3_pattern_usecase import (
    GenerateP3PatternUseCase,
)
from app.domains.ai.application.usecase.generate_p4_akyon_usecase import (
    GenerateP4AkyonUseCase,
)
from app.domains.ai.application.usecase.generate_p4_illusion_usecase import (
    GenerateP4IllusionUseCase,
)
from app.domains.ai.application.usecase.generate_p5_appeal_usecase import (
    GenerateP5AppealUseCase,
)
from app.domains.ai.application.usecase.generate_p5_charm_index_usecase import (
    GenerateP5CharmIndexUseCase,
)
from app.domains.ai.application.usecase.generate_p5_conversion_usecase import (
    GenerateP5ConversionUseCase,
)
from app.domains.ai.application.usecase.generate_p6_meeting_usecase import (
    GenerateP6MeetingUseCase,
)
from app.domains.ai.application.usecase.generate_p6_pattern_usecase import (
    GenerateP6PatternUseCase,
)
from app.domains.ai.application.usecase.generate_p6_profile_usecase import (
    GenerateP6ProfileUseCase,
)
from app.domains.ai.application.usecase.generate_p7_ending_usecase import (
    GenerateP7EndingUseCase,
)
from app.domains.ai.application.usecase.generate_p8_intro_usecase import (
    GenerateP8IntroUseCase,
)
from app.domains.ai.application.usecase.generate_p9_ohang_usecase import (
    GenerateP9OhangUseCase,
)
from app.domains.ai.application.usecase.generate_p9_optimize_usecase import (
    GenerateP9OptimizeUseCase,
)
from app.domains.ai.application.usecase.generate_p9_risk_usecase import (
    GenerateP9RiskUseCase,
)
from app.domains.ai.application.usecase.generate_p10_box1_usecase import (
    GenerateP10Box1UseCase,
)
from app.domains.ai.application.usecase.generate_p10_box2_usecase import (
    GenerateP10Box2UseCase,
)
from app.domains.ai.application.usecase.generate_p10_letter_usecase import (
    GenerateP10LetterUseCase,
)
from app.domains.ai.application.usecase.get_paid_report_usecase import (
    GetPaidReportUseCase,
)
from app.domains.ai.application.usecase.send_result_link_email_usecase import (
    SendResultLinkEmailUseCase,
)
from app.domains.archive.adapter.inbound.api.archive_router import (
    get_archive_usecase,
)
from app.domains.archive.adapter.inbound.api.archive_router import (
    router as archive_router,
)
from app.domains.archive.adapter.outbound.persistence.archive_repository import (
    ArchiveRepository,
)
from app.domains.archive.application.usecase.get_archive_usecase import (
    GetArchiveUseCase,
)
from app.domains.auth.adapter.inbound.api.auth_router import (
    get_delete_account_usecase,
    get_me_usecase,
    get_optional_account_id,
    get_social_login_usecase,
    get_test_login_usecase,
    get_token_issuer,
    get_update_last_used_usecase,
)
from app.domains.auth.adapter.inbound.api.auth_router import (
    router as auth_router,
)
from app.domains.auth.adapter.outbound.external.google_oauth_client import (
    GoogleOAuthClient,
)
from app.domains.auth.adapter.outbound.external.kakao_oauth_client import (
    KakaoOAuthClient,
)
from app.domains.auth.adapter.outbound.persistence.account_deletion_repository import (
    AccountDeletionRepository,
)
from app.domains.auth.adapter.outbound.persistence.account_repository import (
    AccountRepository,
)
from app.domains.auth.application.usecase.delete_account_usecase import (
    DeleteAccountUseCase,
)
from app.domains.auth.application.usecase.get_me_usecase import GetMeUseCase
from app.domains.auth.application.usecase.social_login_usecase import (
    SocialLoginUseCase,
)
from app.domains.auth.application.usecase.test_login_usecase import TestLoginUseCase
from app.domains.auth.application.usecase.update_last_used_usecase import (
    UpdateLastUsedUseCase,
)
from app.domains.auth.domain.port.oauth_client_port import OAuthClientPort
from app.domains.auth.domain.port.token_port import TokenDecodeError
from app.domains.auth.domain.value_object.provider import Provider
from app.domains.chat.adapter.inbound.api.chat_router import (
    get_list_chat_messages_usecase,
    get_list_chat_rooms_usecase,
    get_open_chat_room_usecase,
    get_saju_profile_usecase,
    get_save_saju_profile_usecase,
    get_stream_chat_usecase,
    get_stream_room_chat_usecase,
)
from app.domains.chat.adapter.inbound.api.chat_router import (
    router as chat_router,
)
from app.domains.chat.adapter.outbound.external.claude_chat_client import (
    ClaudeChatClient,
)
from app.domains.chat.adapter.outbound.external.saju_cache_adapter import SajuCacheAdapter
from app.domains.chat.adapter.outbound.persistence.chat_turn_store import ChatTurnStore
from app.domains.chat.adapter.outbound.persistence.conversation_repository import (
    ConversationRepository,
)
from app.domains.chat.adapter.outbound.persistence.saju_profile_repository import (
    SajuProfileRepository,
)
from app.domains.chat.application.usecase.room_usecases import (
    ListChatMessagesUseCase,
    ListChatRoomsUseCase,
    OpenChatRoomUseCase,
)
from app.domains.chat.application.usecase.saju_profile_usecase import (
    GetSajuProfileUseCase,
    SaveSajuProfileUseCase,
)
from app.domains.chat.application.usecase.stream_chat_usecase import StreamChatUseCase
from app.domains.chat.application.usecase.stream_room_chat_usecase import (
    StreamRoomChatUseCase,
)
from app.domains.kkebi.adapter.inbound.api.kkebi_router import (
    get_daily_fortune_usecase,
    get_saved_daily_result_usecase,
)
from app.domains.kkebi.adapter.inbound.api.kkebi_router import (
    router as kkebi_router,
)
from app.domains.kkebi.adapter.outbound.persistence.daily_template_repository import (
    DailyTemplateRepository,
)
from app.domains.kkebi.adapter.outbound.persistence.kkebi_result_repository import (
    KkebiResultRepository,
)
from app.domains.kkebi.application.usecase.get_daily_fortune_usecase import (
    GetDailyFortuneUseCase,
)
from app.domains.kkebi.application.usecase.get_saved_daily_result_usecase import (
    GetSavedDailyResultUseCase,
)
from app.domains.payment.adapter.inbound.api.coupon_router import (
    get_redeem_coupon_usecase,
    get_validate_coupon_usecase,
)
from app.domains.payment.adapter.inbound.api.coupon_router import (
    router as coupon_router,
)
from app.domains.payment.adapter.inbound.api.payment_router import (
    dev_router as payment_dev_router,
)
from app.domains.payment.adapter.inbound.api.payment_router import (
    get_dev_bypass_usecase,
    get_frontend_base_url,
    get_handle_feedback_usecase,
    get_payment_status_usecase,
    get_request_payment_usecase,
    get_update_email_usecase,
)
from app.domains.payment.adapter.inbound.api.payment_router import (
    router as payment_router,
)
from app.domains.payment.adapter.inbound.api.portone_router import (
    get_complete_portone_usecase,
)
from app.domains.payment.adapter.inbound.api.portone_router import (
    router as portone_router,
)
from app.domains.payment.adapter.outbound.external.amplitude_adapter import (
    AmplitudeAnalyticsAdapter,
)
from app.domains.payment.adapter.outbound.external.payapp_client import PayAppClient
from app.domains.payment.adapter.outbound.external.portone_client import PortOneClient
from app.domains.payment.adapter.outbound.persistence.coupon_repository import (
    CouponRepository,
)
from app.domains.payment.adapter.outbound.persistence.payment_repository import (
    PaymentRepository,
)
from app.domains.payment.adapter.outbound.saju_hash_resolver import SajuHashResolver
from app.domains.payment.adapter.outbound.user_demographics_adapter import (
    UserDemographicsAdapter,
)
from app.domains.payment.adapter.outbound.user_lookup_adapter import UserLookupAdapter
from app.domains.payment.application.usecase.complete_portone_payment_usecase import (
    CompletePortOnePaymentUseCase,
)
from app.domains.payment.application.usecase.dev_bypass_payment_usecase import (
    DevBypassPaymentUseCase,
)
from app.domains.payment.application.usecase.email_dispatch_sweeper import (
    EmailDispatchSweeper,
)
from app.domains.payment.application.usecase.get_payment_status_usecase import (
    GetPaymentStatusUseCase,
)
from app.domains.payment.application.usecase.handle_payapp_feedback_usecase import (
    HandlePayAppFeedbackUseCase,
)
from app.domains.payment.application.usecase.redeem_coupon_usecase import (
    RedeemCouponUseCase,
)
from app.domains.payment.application.usecase.request_payment_usecase import (
    RequestPaymentUseCase,
)
from app.domains.payment.application.usecase.update_email_and_resend_usecase import (
    UpdateEmailAndResendUseCase,
)
from app.domains.payment.application.usecase.validate_coupon_usecase import (
    ValidateCouponUseCase,
)
from app.domains.user.adapter.inbound.api.auth import get_user_repository
from app.domains.user.adapter.inbound.api.user_router import (
    get_free_result_usecase,
    get_submit_survey_usecase,
    get_submit_user_info_usecase,
)
from app.domains.user.adapter.inbound.api.user_router import (
    router as user_router,
)
from app.domains.user.adapter.outbound.persistence.saju_result_repository import (
    SajuResultRepository,
)
from app.domains.user.adapter.outbound.persistence.survey_repository import SurveyRepository
from app.domains.user.adapter.outbound.persistence.user_repository import UserRepository
from app.domains.user.application.usecase.get_free_result_usecase import GetFreeResultUseCase
from app.domains.user.application.usecase.submit_survey_usecase import SubmitSurveyUseCase
from app.domains.user.application.usecase.submit_user_info_usecase import SubmitUserInfoUseCase
from app.domains.user.domain.service.blocking_service import BlockingService
from app.domains.user.domain.service.charm_service import CharmService
from app.domains.user.domain.service.monthly_romance_flow_service import MonthlyRomanceFlowService
from app.domains.user.domain.service.saju_data_extractor import SajuDataExtractor
from app.domains.user.domain.service.spouse_avoid_service import SpouseAvoidService
from app.domains.user.domain.service.spouse_match_service import SpouseMatchService
from app.domains.user.infrastructure.fortuneteller_adapter import FortuneTellerAdapter
from app.infrastructure.cache.redis_client import RedisCache
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.external.amplitude.client import AmplitudeClient
from app.infrastructure.external.fortuneteller.client import FortuneTellerClient
from app.infrastructure.external.ses.client import SESClient
from app.infrastructure.security.jwt_provider import JwtTokenProvider

app = FastAPI(title="HailMary Backend", version="0.1.0")

_settings = get_settings()

logger = logging.getLogger(__name__)


def _allowed_origins() -> list[str]:
    # local/test 환경: localhost 프론트 dev 서버 + staging 도메인.
    if _settings.app_env in ("local", "test"):
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://staging.dohwaseonsaju.com",
        ]
    return [
        "https://dohwaseonsaju.com",
        "https://www.dohwaseonsaju.com",
    ]


# CORSMiddleware는 main.py 가장 마지막에 add — Starlette 미들웨어는 LIFO라
# 가장 마지막 add가 가장 바깥(=모든 응답에 CORS 헤더 박힘). 이 위치에서 add 금지.


# ── DB 세션 ──────────────────────────────────────────────────────────────────

async def _get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session, session.begin():
        yield session


# ── FortuneTeller ─────────────────────────────────────────────────────────────

def _get_ft_adapter() -> FortuneTellerAdapter:
    return FortuneTellerAdapter(FortuneTellerClient(base_url=_settings.fortuneteller_url))


# ── Redis 캐시 (HM-BE-67, 깨비 일일사주) ─────────────────────────────────────
# 싱글톤 인스턴스. cache_enabled=False면 None 반환 → UseCase가 캐시 우회.
_redis_cache_instance: RedisCache | None = (
    RedisCache(_settings.redis_url) if _settings.cache_enabled else None
)


def _get_redis_cache() -> RedisCache | None:
    return _redis_cache_instance


# ── Auth Domain (소셜 로그인, HM-BE-77) ──────────────────────────────────────
# JWT provider/OAuth 클라이언트는 stateless — 모듈 로드 시 1회 구성.
# 키 미설정 환경(예: 시크릿 등록 전 staging)에서도 앱은 뜨고 /api/auth/*만 비활성.

_token_provider_instance: JwtTokenProvider | None = (
    JwtTokenProvider(secret=_settings.jwt_secret, expires_days=_settings.jwt_expires_days)
    if _settings.jwt_secret
    else None
)


def _get_token_provider() -> JwtTokenProvider:
    if _token_provider_instance is None:
        raise HTTPException(
            status_code=503, detail="로그인 기능이 설정되지 않았습니다 (JWT_SECRET 미설정)"
        )
    return _token_provider_instance


def _build_oauth_clients() -> dict[Provider, OAuthClientPort]:
    # Windows 로컬은 asyncmy 동봉 OpenSSL 충돌로 SSLContext 생성이 크래시(OPENSSL_Uplink)
    # → local 환경에서만 TLS 검증 비활성 (PayApp verify=False 선례). staging/prod는 검증 유지.
    verify_tls = _settings.app_env != "local"
    clients: dict[Provider, OAuthClientPort] = {}
    if _settings.kakao_client_id and _settings.kakao_client_secret:
        clients[Provider.KAKAO] = KakaoOAuthClient(
            client_id=_settings.kakao_client_id,
            client_secret=_settings.kakao_client_secret,
            verify_tls=verify_tls,
        )
    if _settings.google_client_id and _settings.google_client_secret:
        clients[Provider.GOOGLE] = GoogleOAuthClient(
            client_id=_settings.google_client_id,
            client_secret=_settings.google_client_secret,
            verify_tls=verify_tls,
        )
    return clients


_oauth_clients: dict[Provider, OAuthClientPort] = _build_oauth_clients()


def _make_social_login_usecase(
    session: AsyncSession = Depends(_get_session),
) -> SocialLoginUseCase:
    return SocialLoginUseCase(
        oauth_clients=_oauth_clients,
        account_repo=AccountRepository(session),
        token_issuer=_get_token_provider(),
    )


def _make_test_login_usecase(
    session: AsyncSession = Depends(_get_session),
) -> TestLoginUseCase:
    # 카드사 심사용. test_login_enabled=False면 usecase가 404(없는 것처럼) 반환.
    return TestLoginUseCase(
        account_repo=AccountRepository(session),
        token_issuer=_get_token_provider(),
        enabled=_settings.test_login_enabled,
        username=_settings.test_login_username,
        password=_settings.test_login_password,
    )


def _make_get_me_usecase(
    session: AsyncSession = Depends(_get_session),
) -> GetMeUseCase:
    return GetMeUseCase(account_repo=AccountRepository(session))


def _make_update_last_used_usecase(
    session: AsyncSession = Depends(_get_session),
) -> UpdateLastUsedUseCase:
    return UpdateLastUsedUseCase(account_repo=AccountRepository(session))


def _make_delete_account_usecase(
    session: AsyncSession = Depends(_get_session),
) -> DeleteAccountUseCase:
    return DeleteAccountUseCase(deletion=AccountDeletionRepository(session))


async def _optional_account_id(request: Request) -> int | None:
    """선택적 계정 인지 — JWT 미설정/누락/위조면 None (401 안 던짐). /api/kkebi/fortune 등."""
    if _token_provider_instance is None:
        return None
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):].strip()
    if not token:
        return None
    try:
        return _token_provider_instance.decode(token)
    except TokenDecodeError:
        return None


# ── 인증 의존성용 UserRepository 팩토리 ───────────────────────────────────────

def _make_user_repository(
    session: AsyncSession = Depends(_get_session),
) -> UserRepository:
    return UserRepository(session)


# ── User Domain UseCase 팩토리 ────────────────────────────────────────────────

def _make_submit_user_info_usecase(
    session: AsyncSession = Depends(_get_session),
    ft: FortuneTellerAdapter = Depends(_get_ft_adapter),
) -> SubmitUserInfoUseCase:
    return SubmitUserInfoUseCase(
        user_repo=UserRepository(session),
        saju_result_repo=SajuResultRepository(session),
        fortuneteller=ft,
        saju_data_extractor=SajuDataExtractor(),
        charm_service=CharmService(),
        blocking_service=BlockingService(),
        spouse_avoid_service=SpouseAvoidService(),
        spouse_match_service=SpouseMatchService(),
        monthly_romance_flow_service=MonthlyRomanceFlowService(),
    )


def _make_submit_survey_usecase(
    session: AsyncSession = Depends(_get_session),
) -> SubmitSurveyUseCase:
    return SubmitSurveyUseCase(
        survey_repo=SurveyRepository(session),
        saju_result_repo=SajuResultRepository(session),
    )


def _make_get_free_result_usecase(
    session: AsyncSession = Depends(_get_session),
) -> GetFreeResultUseCase:
    return GetFreeResultUseCase(
        saju_result_repo=SajuResultRepository(session),
        charm_service=CharmService(),
        blocking_service=BlockingService(),
        spouse_avoid_service=SpouseAvoidService(),
        spouse_match_service=SpouseMatchService(),
        monthly_romance_flow_service=MonthlyRomanceFlowService(),
    )


# ── 깨비 일일사주(kkebi) UseCase 팩토리 ───────────────────────────────────────

def _make_get_daily_fortune_usecase(
    session: AsyncSession = Depends(_get_session),
    ft: FortuneTellerAdapter = Depends(_get_ft_adapter),
) -> GetDailyFortuneUseCase:
    return GetDailyFortuneUseCase(
        fortuneteller=ft,
        template_repo=DailyTemplateRepository(session),
        cache=_get_redis_cache(),
        pillars_ttl_seconds=_settings.kkebi_pillars_ttl_seconds,
        result_ttl_seconds=_settings.kkebi_result_ttl_seconds,
        result_repo=KkebiResultRepository(session),  # 로그인 시 결과 저장 (HM-BE-79)
    )


def _make_get_saved_daily_result_usecase(
    session: AsyncSession = Depends(_get_session),
) -> GetSavedDailyResultUseCase:
    return GetSavedDailyResultUseCase(result_repo=KkebiResultRepository(session))


def _make_get_archive_usecase(
    session: AsyncSession = Depends(_get_session),
) -> GetArchiveUseCase:
    return GetArchiveUseCase(archive_repo=ArchiveRepository(session))


# ── Payment Domain UseCase 팩토리 ────────────────────────────────────────────

def _make_payapp_client() -> PayAppClient:
    """PayApp 클라이언트 싱글톤 팩토리. Phase 2 endpoint들에서 Depends로 주입."""
    missing: list[str] = []
    if not _settings.payapp_userid:
        missing.append("PAYAPP_USERID")
    if not _settings.payapp_linkkey:
        missing.append("PAYAPP_LINKKEY")
    if not _settings.payapp_linkval:
        missing.append("PAYAPP_LINKVAL")
    if not _settings.payapp_feedback_url:
        missing.append("PAYAPP_FEEDBACK_URL")
    if not _settings.payapp_return_url:
        missing.append("PAYAPP_RETURN_URL")
    if missing:
        raise RuntimeError(
            f"PayApp 환경변수가 설정되지 않았습니다: {', '.join(missing)}"
        )
    # Settings에서 None 체크 통과한 값은 모두 str — mypy 만족용 cast 대신 assert
    assert _settings.payapp_userid is not None
    assert _settings.payapp_linkkey is not None
    assert _settings.payapp_linkval is not None
    assert _settings.payapp_feedback_url is not None
    assert _settings.payapp_return_url is not None
    return PayAppClient(
        userid=_settings.payapp_userid,
        linkkey=_settings.payapp_linkkey,
        linkval=_settings.payapp_linkval,
        base_url=_settings.payapp_base_url,
        feedback_url=_settings.payapp_feedback_url,
        return_url=_settings.payapp_return_url,
    )


def _build_paid_report_pipeline(
    session: AsyncSession,
) -> tuple[CreatePaidReportUseCase, SajuHashResolver, UserLookupAdapter, UserDemographicsAdapter, "AmplitudeAnalyticsAdapter"]:
    """결제 완료 후 트리거되는 PaidReport 합성 + 사용자 룩업 + 분석 파이프라인.

    PayApp feedback UseCase에서 사용.
    """
    paid_report_repo = PaidReportRepository(session)
    # P-10 AI 호출용 Claude 클라이언트 (키 있을 때만, 없으면 폴백)
    p10_letter_usecase: GenerateP10LetterUseCase | None = None
    # 도윤 P-0 ai_intro + P-1 3슬롯 AI (같은 클라이언트 공유, model은 sonnet 통일)
    p0_diagnosis_usecase: GenerateP0DiagnosisUseCase | None = None
    p1_opening_usecase: GenerateP1OpeningUseCase | None = None
    p1_trigger_usecase: GenerateP1TriggerUseCase | None = None
    p1_emotion_usecase: GenerateP1EmotionUseCase | None = None
    p2_hurt_usecase: GenerateP2HurtUseCase | None = None
    p2_recovery_usecase: GenerateP2RecoveryUseCase | None = None
    p3_blockade_usecase: GenerateP3BlockadeUseCase | None = None
    p3_pattern_usecase: GenerateP3PatternUseCase | None = None
    p4_akyon_usecase: GenerateP4AkyonUseCase | None = None
    p4_illusion_usecase: GenerateP4IllusionUseCase | None = None
    p5_charm_index_usecase: GenerateP5CharmIndexUseCase | None = None
    p5_conversion_usecase: GenerateP5ConversionUseCase | None = None
    p5_appeal_usecase: GenerateP5AppealUseCase | None = None
    p6_profile_usecase: GenerateP6ProfileUseCase | None = None
    p6_meeting_usecase: GenerateP6MeetingUseCase | None = None
    p6_pattern_usecase: GenerateP6PatternUseCase | None = None
    p7_ending_usecase: GenerateP7EndingUseCase | None = None
    p8_intro_usecase: GenerateP8IntroUseCase | None = None
    p9_ohang_usecase: GenerateP9OhangUseCase | None = None
    p9_risk_usecase: GenerateP9RiskUseCase | None = None
    p9_optimize_usecase: GenerateP9OptimizeUseCase | None = None
    p10_box1_usecase: GenerateP10Box1UseCase | None = None
    p10_box2_usecase: GenerateP10Box2UseCase | None = None
    determine_name_address_usecase: DetermineDoyoonNameAddressUseCase | None = None
    if _settings.claude_api_key:
        claude_client = ClaudeClient(
            api_key=_settings.claude_api_key,
            model=_settings.claude_model,
        )
        p10_letter_usecase = GenerateP10LetterUseCase(ai_client=claude_client)
        p0_diagnosis_usecase = GenerateP0DiagnosisUseCase(ai_client=claude_client)
        p1_opening_usecase = GenerateP1OpeningUseCase(ai_client=claude_client)
        p1_trigger_usecase = GenerateP1TriggerUseCase(ai_client=claude_client)
        p1_emotion_usecase = GenerateP1EmotionUseCase(ai_client=claude_client)
        p2_hurt_usecase = GenerateP2HurtUseCase(ai_client=claude_client)
        p2_recovery_usecase = GenerateP2RecoveryUseCase(ai_client=claude_client)
        p3_blockade_usecase = GenerateP3BlockadeUseCase(ai_client=claude_client)
        p3_pattern_usecase = GenerateP3PatternUseCase(ai_client=claude_client)
        p4_akyon_usecase = GenerateP4AkyonUseCase(ai_client=claude_client)
        p4_illusion_usecase = GenerateP4IllusionUseCase(ai_client=claude_client)
        p5_charm_index_usecase = GenerateP5CharmIndexUseCase(ai_client=claude_client)
        p5_conversion_usecase = GenerateP5ConversionUseCase(ai_client=claude_client)
        p5_appeal_usecase = GenerateP5AppealUseCase(ai_client=claude_client)
        p6_profile_usecase = GenerateP6ProfileUseCase(ai_client=claude_client)
        p6_meeting_usecase = GenerateP6MeetingUseCase(ai_client=claude_client)
        p6_pattern_usecase = GenerateP6PatternUseCase(ai_client=claude_client)
        p7_ending_usecase = GenerateP7EndingUseCase(ai_client=claude_client)
        p8_intro_usecase = GenerateP8IntroUseCase(ai_client=claude_client)
        p9_ohang_usecase = GenerateP9OhangUseCase(ai_client=claude_client)
        p9_risk_usecase = GenerateP9RiskUseCase(ai_client=claude_client)
        p9_optimize_usecase = GenerateP9OptimizeUseCase(ai_client=claude_client)
        p10_box1_usecase = GenerateP10Box1UseCase(ai_client=claude_client)
        p10_box2_usecase = GenerateP10Box2UseCase(ai_client=claude_client)
        determine_name_address_usecase = DetermineDoyoonNameAddressUseCase(ai_client=claude_client)
    # SES 이메일 발송 (sender + IAM 키 있을 때만, 없으면 폴백)
    email_sender: SendResultLinkEmailUseCase | None = None
    if _settings.aws_ses_sender:
        ses_client = SESClient(
            region=_settings.aws_region,
            sender=_settings.aws_ses_sender,
            access_key_id=_settings.aws_access_key_id,
            secret_access_key=_settings.aws_secret_access_key,
        )
        # 결과지 링크 base URL — 환경 설정값 사용 (local=localhost, staging/prod=FRONTEND_BASE_URL)
        base_url = _settings.frontend_base_url
        email_sender = SendResultLinkEmailUseCase(
            ses_client=ses_client,
            base_url=base_url,
        )
    user_repo = UserRepository(session)
    create_paid_report_usecase = CreatePaidReportUseCase(
        paid_report_repo=paid_report_repo,
        saju_result_repo=SajuResultRepository(session),
        survey_repo=SurveyRepository(session),
        compose_usecase=ComposePaidReportUseCase(),
        p10_letter_usecase=p10_letter_usecase,
        determine_name_address_usecase=determine_name_address_usecase,
        p0_diagnosis_usecase=p0_diagnosis_usecase,
        p1_opening_usecase=p1_opening_usecase,
        p1_trigger_usecase=p1_trigger_usecase,
        p1_emotion_usecase=p1_emotion_usecase,
        p2_hurt_usecase=p2_hurt_usecase,
        p2_recovery_usecase=p2_recovery_usecase,
        p3_blockade_usecase=p3_blockade_usecase,
        p3_pattern_usecase=p3_pattern_usecase,
        p4_akyon_usecase=p4_akyon_usecase,
        p4_illusion_usecase=p4_illusion_usecase,
        p5_charm_index_usecase=p5_charm_index_usecase,
        p5_conversion_usecase=p5_conversion_usecase,
        p5_appeal_usecase=p5_appeal_usecase,
        p6_profile_usecase=p6_profile_usecase,
        p6_meeting_usecase=p6_meeting_usecase,
        p6_pattern_usecase=p6_pattern_usecase,
        p7_ending_usecase=p7_ending_usecase,
        p8_intro_usecase=p8_intro_usecase,
        p9_ohang_usecase=p9_ohang_usecase,
        p9_risk_usecase=p9_risk_usecase,
        p9_optimize_usecase=p9_optimize_usecase,
        p10_box1_usecase=p10_box1_usecase,
        p10_box2_usecase=p10_box2_usecase,
        email_sender=email_sender,
        user_repo=user_repo,
    )
    saju_hash_resolver = SajuHashResolver(
        user_repo=user_repo,
        saju_result_repo=SajuResultRepository(session),
    )
    user_lookup = UserLookupAdapter(user_repo=user_repo)
    user_demographics = UserDemographicsAdapter(user_repo=user_repo)
    analytics = AmplitudeAnalyticsAdapter(
        client=AmplitudeClient(
            api_key=_settings.amplitude_api_key,
            base_url=_settings.amplitude_base_url,
        ),
        environment=_settings.app_env,
    )
    return create_paid_report_usecase, saju_hash_resolver, user_lookup, user_demographics, analytics


class _TestAccountChecker:
    """request_payment용 어댑터 — test_login_enabled AND account.provider==TEST 면 테스트 계정.

    플래그 off면 항상 False → 심사 종료 후 0원 발급 경로 완전 차단.
    """

    def __init__(self, account_repo: AccountRepository, enabled: bool) -> None:
        self._account_repo = account_repo
        self._enabled = enabled

    async def is_test_account(self, account_id: int | None) -> bool:
        if not self._enabled or account_id is None:
            return False
        account = await self._account_repo.find_by_id(account_id)
        return account is not None and account.provider == Provider.TEST


def _make_request_payment_usecase(
    session: AsyncSession = Depends(_get_session),
) -> RequestPaymentUseCase:
    user_repo = UserRepository(session)
    return RequestPaymentUseCase(
        gateway=_make_payapp_client(),
        repo=PaymentRepository(session),
        user_lookup=UserLookupAdapter(user_repo=user_repo),
        account_checker=_TestAccountChecker(
            AccountRepository(session), _settings.test_login_enabled
        ),
        background_composer=_compose_report_background,
    )


def _make_handle_feedback_usecase(
    session: AsyncSession = Depends(_get_session),
) -> HandlePayAppFeedbackUseCase:
    if not _settings.payapp_linkkey or not _settings.payapp_linkval:
        raise RuntimeError(
            "PAYAPP_LINKKEY/PAYAPP_LINKVAL 환경변수가 설정되지 않았습니다."
        )
    # 합성은 백그라운드(_compose_report_background, 자기 DB 세션)로 분리 — 쿠폰 경로와 동일.
    # 요청 세션엔 analytics/demographics 만(Amplitude inline, 빠름). 합성 inline await 제거로
    # DONE 즉시 커밋 → 이메일 팝업/결과 로딩이 합성을 가려주는 원래 UX 복원 + checkretry 중복 위험↓.
    _creator, _resolver, _user_lookup, user_demographics, analytics = _build_paid_report_pipeline(session)
    return HandlePayAppFeedbackUseCase(
        repo=PaymentRepository(session),
        expected_linkkey=_settings.payapp_linkkey,
        expected_linkval=_settings.payapp_linkval,
        background_composer=_compose_report_background,
        analytics=analytics,
        user_demographics=user_demographics,
    )


def _make_complete_portone_usecase(
    session: AsyncSession = Depends(_get_session),
) -> CompletePortOnePaymentUseCase:
    # 합성은 백그라운드(_compose_report_background, 자기 세션) — 요청 세션엔 analytics/demographics 만.
    _creator, _resolver, _ul, user_demographics, analytics = _build_paid_report_pipeline(
        session
    )
    return CompletePortOnePaymentUseCase(
        portone=PortOneClient(
            api_secret=_settings.portone_api_secret or "",
            webhook_secret=_settings.portone_webhook_secret,
        ),
        repo=PaymentRepository(session),
        user_lookup=UserLookupAdapter(user_repo=UserRepository(session)),
        background_composer=_compose_report_background,
        analytics=analytics,
        user_demographics=user_demographics,
        allow_test_channel=_settings.portone_allow_test_channel,
    )


def _make_payment_status_usecase(
    session: AsyncSession = Depends(_get_session),
) -> GetPaymentStatusUseCase:
    return GetPaymentStatusUseCase(repo=PaymentRepository(session))


def _make_update_email_usecase(
    session: AsyncSession = Depends(_get_session),
) -> UpdateEmailAndResendUseCase:
    """결제 후 이메일 수정 + 메일 재발송. SES sender 없으면 메일 단계만 no-op로 폴백."""
    paid_report_repo = PaidReportRepository(session)

    class _ShareLookupAdapter:
        async def find_share_code(self, order_id: str) -> str | None:
            r = await paid_report_repo.find_by_order_id(order_id)
            return r.share_code if r else None

    # email_resend: SES 설정되어 있을 때만 실 발송, 아니면 no-op (메일 수정만 반영)
    email_resend_impl: object
    if _settings.aws_ses_sender:
        ses_client = SESClient(
            region=_settings.aws_region,
            sender=_settings.aws_ses_sender,
            access_key_id=_settings.aws_access_key_id,
            secret_access_key=_settings.aws_secret_access_key,
        )
        base_url = _settings.frontend_base_url
        email_resend_impl = SendResultLinkEmailUseCase(
            ses_client=ses_client, base_url=base_url
        )
    else:
        class _NoopResend:
            async def execute(self, **_: object) -> None:
                return None
        email_resend_impl = _NoopResend()

    return UpdateEmailAndResendUseCase(
        payment_repo=PaymentRepository(session),
        share_lookup=_ShareLookupAdapter(),
        email_resend=email_resend_impl,
    )


def _make_dev_bypass_usecase(
    session: AsyncSession = Depends(_get_session),
) -> DevBypassPaymentUseCase:
    user_repo = UserRepository(session)
    creator, resolver, _user_lookup, user_demographics, analytics = _build_paid_report_pipeline(session)
    return DevBypassPaymentUseCase(
        repo=PaymentRepository(session),
        user_lookup=UserLookupAdapter(user_repo=user_repo),
        paid_report_creator=creator,
        saju_hash_resolver=resolver,
        analytics=analytics,
        user_demographics=user_demographics,
    )


# ── 무료 쿠폰 UseCase 팩토리 (prod 노출 — 코드가 가드) ───────────────────────

def _compose_report_background(
    *,
    order_id: str,
    user_id: int,
    customer_email: str,
    expires_at: datetime,
    character: str,
) -> Coroutine[Any, Any, None]:
    """쿠폰 무료 발급 후 유료 결과지 합성을 백그라운드에서 수행.

    요청 세션은 응답과 함께 닫히므로 **자기 AsyncSession 을 새로 연다**(이메일
    fire-and-forget 과 동일 계열). 도윤의 긴 AI 합성이 redeem 응답을 막지 않게 분리.
    """

    async def _run() -> None:
        try:
            async with AsyncSessionLocal() as session, session.begin():
                creator, resolver, _ul, _ud, _an = _build_paid_report_pipeline(session)
                saju_hash = await resolver.resolve(user_id)
                await creator.execute(
                    order_id=order_id,
                    saju_hash=saju_hash or order_id,
                    user_id=user_id,
                    customer_email=customer_email,
                    expires_at=expires_at,
                    character=character,
                )
        except Exception:
            logger.exception("[COUPON bg compose] failed order=%s", order_id)

    return _run()


def _make_redeem_coupon_usecase(
    session: AsyncSession = Depends(_get_session),
) -> RedeemCouponUseCase:
    user_repo = UserRepository(session)
    # 합성은 백그라운드(자기 세션)에서 — 여기선 analytics/demographics 만 요청 세션으로.
    analytics = AmplitudeAnalyticsAdapter(
        client=AmplitudeClient(
            api_key=_settings.amplitude_api_key,
            base_url=_settings.amplitude_base_url,
        ),
        environment=_settings.app_env,
    )
    return RedeemCouponUseCase(
        coupon_repo=CouponRepository(session),
        repo=PaymentRepository(session),
        user_lookup=UserLookupAdapter(user_repo=user_repo),
        background_composer=_compose_report_background,
        analytics=analytics,
        user_demographics=UserDemographicsAdapter(user_repo=user_repo),
    )


def _make_validate_coupon_usecase(
    session: AsyncSession = Depends(_get_session),
) -> ValidateCouponUseCase:
    return ValidateCouponUseCase(coupon_repo=CouponRepository(session))


# ── AI Domain UseCase 팩토리 ──────────────────────────────────────────────────

def _make_get_paid_report_usecase(
    session: AsyncSession = Depends(_get_session),
) -> GetPaidReportUseCase:
    return GetPaidReportUseCase(
        paid_report_repo=PaidReportRepository(session),
        payment_repo=PaymentRepository(session),
        user_repo=UserRepository(session),
    )


# ── Chat Domain UseCase 팩토리 (도화선 2.0, HM-BE-86·87) ─────────────────────

# 스트리밍 클라이언트는 모듈 싱글턴 — 요청마다 AsyncAnthropic 재생성 방지.
_chat_client_instance: ClaudeChatClient | None = (
    ClaudeChatClient(api_key=_settings.claude_api_key, model=_settings.claude_model)
    if _settings.chat_enabled and _settings.claude_api_key
    else None
)


def _make_stream_chat_usecase() -> StreamChatUseCase:
    # chat_enabled=True + claude_api_key 설정 시에만 라우터가 등록되므로 여기 도달 시 존재 보장.
    if _chat_client_instance is None:
        raise HTTPException(status_code=503, detail="chat 미설정 (chat_enabled/claude_api_key)")
    return StreamChatUseCase(
        chat_client=_chat_client_instance,
        max_tokens=_settings.chat_max_tokens,
        history_window=_settings.chat_history_window,
        temperature=_settings.chat_temperature,
    )


# 스트리밍 턴 영속화 — 요청 세션이 아닌 자체 단명 세션 (CHAT_SSOT.md SSE 계약).
_chat_turn_store = ChatTurnStore(AsyncSessionLocal)


def _make_stream_room_chat_usecase() -> StreamRoomChatUseCase:
    if _chat_client_instance is None:
        raise HTTPException(status_code=503, detail="chat 미설정 (chat_enabled/claude_api_key)")
    return StreamRoomChatUseCase(
        chat_client=_chat_client_instance,
        turn_store=_chat_turn_store,
        max_tokens=_settings.chat_max_tokens,
        history_window=_settings.chat_history_window,
        temperature=_settings.chat_temperature,
    )


def _make_list_chat_rooms_usecase(
    session: AsyncSession = Depends(_get_session),
) -> ListChatRoomsUseCase:
    return ListChatRoomsUseCase(conversation_repo=ConversationRepository(session))


def _make_open_chat_room_usecase(
    session: AsyncSession = Depends(_get_session),
) -> OpenChatRoomUseCase:
    return OpenChatRoomUseCase(conversation_repo=ConversationRepository(session))


def _make_list_chat_messages_usecase(
    session: AsyncSession = Depends(_get_session),
) -> ListChatMessagesUseCase:
    return ListChatMessagesUseCase(conversation_repo=ConversationRepository(session))


def _make_get_saju_profile_usecase(
    session: AsyncSession = Depends(_get_session),
) -> GetSajuProfileUseCase:
    return GetSajuProfileUseCase(profile_repo=SajuProfileRepository(session))


def _make_save_saju_profile_usecase(
    session: AsyncSession = Depends(_get_session),
) -> SaveSajuProfileUseCase:
    return SaveSajuProfileUseCase(
        profile_repo=SajuProfileRepository(session),
        saju_engine=_get_ft_adapter(),
        cache=SajuCacheAdapter(_redis_cache_instance, _settings.chat_saju_cache_ttl_seconds),
    )


# ── 의존성 오버라이드 ──────────────────────────────────────────────────────────

app.dependency_overrides[get_user_repository] = _make_user_repository
app.dependency_overrides[get_submit_user_info_usecase] = _make_submit_user_info_usecase
app.dependency_overrides[get_submit_survey_usecase] = _make_submit_survey_usecase
app.dependency_overrides[get_free_result_usecase] = _make_get_free_result_usecase
app.dependency_overrides[get_daily_fortune_usecase] = _make_get_daily_fortune_usecase
app.dependency_overrides[get_saved_daily_result_usecase] = _make_get_saved_daily_result_usecase
app.dependency_overrides[get_optional_account_id] = _optional_account_id
app.dependency_overrides[get_archive_usecase] = _make_get_archive_usecase
app.dependency_overrides[get_request_payment_usecase] = _make_request_payment_usecase
app.dependency_overrides[get_handle_feedback_usecase] = _make_handle_feedback_usecase
app.dependency_overrides[get_payment_status_usecase] = _make_payment_status_usecase
app.dependency_overrides[get_complete_portone_usecase] = _make_complete_portone_usecase
app.dependency_overrides[get_update_email_usecase] = _make_update_email_usecase
app.dependency_overrides[get_dev_bypass_usecase] = _make_dev_bypass_usecase
app.dependency_overrides[get_redeem_coupon_usecase] = _make_redeem_coupon_usecase
app.dependency_overrides[get_validate_coupon_usecase] = _make_validate_coupon_usecase
app.dependency_overrides[get_frontend_base_url] = lambda: _settings.frontend_base_url
app.dependency_overrides[get_paid_report_usecase] = _make_get_paid_report_usecase
app.dependency_overrides[get_social_login_usecase] = _make_social_login_usecase
app.dependency_overrides[get_test_login_usecase] = _make_test_login_usecase
app.dependency_overrides[get_me_usecase] = _make_get_me_usecase
app.dependency_overrides[get_update_last_used_usecase] = _make_update_last_used_usecase
app.dependency_overrides[get_delete_account_usecase] = _make_delete_account_usecase
app.dependency_overrides[get_token_issuer] = _get_token_provider
app.dependency_overrides[get_stream_chat_usecase] = _make_stream_chat_usecase
app.dependency_overrides[get_stream_room_chat_usecase] = _make_stream_room_chat_usecase
app.dependency_overrides[get_list_chat_rooms_usecase] = _make_list_chat_rooms_usecase
app.dependency_overrides[get_open_chat_room_usecase] = _make_open_chat_room_usecase
app.dependency_overrides[get_list_chat_messages_usecase] = _make_list_chat_messages_usecase
app.dependency_overrides[get_saju_profile_usecase] = _make_get_saju_profile_usecase
app.dependency_overrides[get_save_saju_profile_usecase] = _make_save_saju_profile_usecase

app.include_router(user_router)
app.include_router(auth_router)
app.include_router(archive_router)
app.include_router(payment_router)
# 포트원 카카오페이 — portone_enabled=True 일 때만 등록 (미설정 시 엔드포인트 404, 완전 차단).
if _settings.portone_enabled:
    app.include_router(portone_router)
app.include_router(paid_report_router)
app.include_router(kkebi_router)
# 도화선 2.0 캐릭터 챗 — chat_enabled=True 일 때만 등록 (미설정 시 404, 완전 차단).
# staging은 main push 자동 배포라 이 게이트가 미완성 노출 방어선 (CHAT_SSOT.md).
if _settings.chat_enabled:
    app.include_router(chat_router)
app.include_router(paid_report_share_router)
# 무료 쿠폰 — dev bypass 와 달리 환경 가드 없이 항상 등록(prod 포함).
# 유효 쿠폰 코드 자체가 가드 역할 → _DEV_BYPASS_ENVS 분기에 넣지 말 것.
app.include_router(coupon_router)

# ⚠️ 결제 패스 endpoint — prod 환경에서는 등록 안 함. staging/local/test 에서만 노출.
# 워크플로마다 APP_ENV 값 다를 수 있음 (prod 워크플로는 "production") — 명시 화이트리스트로 비교.
_DEV_BYPASS_ENVS = {"local", "test", "staging"}
if _settings.app_env.lower() in _DEV_BYPASS_ENVS:
    app.include_router(payment_dev_router)

# QA 로그인 게이트 — APP_ENV=test 일 때만 등록 (운영 환경 무영향)
if _settings.app_env == "test":
    from app.domains.qa_auth.router import router as qa_auth_router
    from app.middleware.qa_auth import QaAuthMiddleware

    app.include_router(qa_auth_router)
    if _settings.qa_access_token:
        app.add_middleware(QaAuthMiddleware, expected_token=_settings.qa_access_token)


# CORS 미들웨어는 항상 마지막에 add — LIFO 스택의 가장 바깥에 위치해야
# QaAuthMiddleware가 401 던져도 응답에 CORS 헤더가 박힘.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=False,
    # DELETE 누락 시 회원탈퇴(DELETE /api/auth/me) 브라우저 프리플라이트가 400(Disallowed CORS method)로 막힘 → HM-BE-82 후속 수정.
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-QA-Token"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── 결과지 메일 발송 스위퍼 (확정-후-발송 설계, 2026-06-05) ──────────────────
# 발송 주체는 ① /update-email 확정 ② 본 스위퍼(확정 건 즉시 / 미확정 grace 폴백).
# 상태가 전부 DB(email_confirmed_at/result_email_sent_at)라 재시작에도 안전.

_EMAIL_SWEEPER_INTERVAL_SECONDS = 30
_email_sweeper_task: asyncio.Task[None] | None = None


async def _email_sweeper_tick() -> None:
    async with AsyncSessionLocal() as session, session.begin():
        paid_report_repo = PaidReportRepository(session)

        class _ShareLookupAdapter:
            async def find_share_code(self, order_id: str) -> str | None:
                r = await paid_report_repo.find_by_order_id(order_id)
                return r.share_code if r else None

        if not _settings.aws_ses_sender:
            return  # SES 미설정(로컬 등) — 발송 자체가 no-op이므로 스킵
        ses_client = SESClient(
            region=_settings.aws_region,
            sender=_settings.aws_ses_sender,
            access_key_id=_settings.aws_access_key_id,
            secret_access_key=_settings.aws_secret_access_key,
        )
        sweeper = EmailDispatchSweeper(
            payment_repo=PaymentRepository(session),
            share_lookup=_ShareLookupAdapter(),
            email_resend=SendResultLinkEmailUseCase(
                ses_client=ses_client, base_url=_settings.frontend_base_url
            ),
        )
        sent = await sweeper.run_once()
        if sent:
            logger.info("[email-sweeper] dispatched %d result link email(s)", sent)


async def _email_sweeper_loop() -> None:
    while True:
        try:
            await _email_sweeper_tick()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — 틱 실패가 루프를 죽이지 않게
            logger.exception("[email-sweeper] tick failed")
        await asyncio.sleep(_EMAIL_SWEEPER_INTERVAL_SECONDS)


@app.on_event("startup")
async def _start_email_sweeper() -> None:
    # asyncio task GC 가드 — 모듈 레벨 참조로 보관 (fire-and-forget GC 함정).
    global _email_sweeper_task
    _email_sweeper_task = asyncio.create_task(_email_sweeper_loop())


@app.on_event("shutdown")
async def _stop_email_sweeper() -> None:
    if _email_sweeper_task is not None:
        _email_sweeper_task.cancel()
