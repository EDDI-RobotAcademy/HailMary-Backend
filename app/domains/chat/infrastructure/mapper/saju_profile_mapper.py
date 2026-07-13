from app.domains.chat.domain.entity.saju_profile import SajuProfile
from app.domains.chat.domain.value_object.birth_profile import (
    BirthProfile,
    SajuCalendar,
    SajuGender,
)
from app.domains.chat.infrastructure.orm.saju_profile_orm import SajuProfileORM


class SajuProfileMapper:
    @staticmethod
    def to_entity(orm: SajuProfileORM) -> SajuProfile:
        return SajuProfile(
            id=orm.id,
            account_id=orm.account_id,
            birth=BirthProfile(
                birth_date=orm.birth_date,
                birth_time=orm.birth_time,
                time_unknown=orm.birth_time_unknown,
                calendar=SajuCalendar(orm.calendar),
                gender=SajuGender(orm.gender),
            ),
            saju_raw=orm.saju_raw,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )
