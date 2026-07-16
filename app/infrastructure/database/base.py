from app.domains.ai.infrastructure.orm.paid_report_orm import PaidReportORM  # noqa: F401
from app.domains.auth.infrastructure.orm.account_orm import AccountORM  # noqa: F401
from app.domains.chat.infrastructure.orm.chat_message_orm import ChatMessageORM  # noqa: F401
from app.domains.chat.infrastructure.orm.conversation_orm import ConversationORM  # noqa: F401
from app.domains.chat.infrastructure.orm.saju_profile_orm import SajuProfileORM  # noqa: F401
from app.domains.kkebi.infrastructure.orm.kkebi_result_orm import KkebiResultORM  # noqa: F401
from app.domains.payment.infrastructure.orm.coupon_orm import CouponORM  # noqa: F401
from app.domains.payment.infrastructure.orm.payment_orm import PaymentORM  # noqa: F401
from app.domains.user.infrastructure.orm.saju_result_orm import SajuResultORM  # noqa: F401
from app.domains.user.infrastructure.orm.survey_orm import SurveyORM  # noqa: F401

# Alembic이 모든 테이블을 자동 탐색할 수 있도록 ORM 모델을 import한다.
from app.domains.user.infrastructure.orm.user_orm import UserORM  # noqa: F401
from app.infrastructure.database.session import Base

__all__ = ["Base"]
