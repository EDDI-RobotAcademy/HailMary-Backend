from pydantic import BaseModel, Field

from app.domains.chat.domain.value_object.birth_profile import (
    BirthProfile,
    SajuCalendar,
    SajuGender,
)


class SaveSajuProfileRequest(BaseModel):
    """확인 모달에서 확정된 생년월일시. (FE는 /api/auth/me last_used로 프리필)"""

    birth_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    birth_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    birth_time_unknown: bool = False
    calendar: SajuCalendar = SajuCalendar.SOLAR
    gender: SajuGender

    def to_birth_profile(self) -> BirthProfile:
        return BirthProfile(
            birth_date=self.birth_date,
            birth_time=self.birth_time,
            time_unknown=self.birth_time_unknown or self.birth_time is None,
            calendar=self.calendar,
            gender=self.gender,
        )
