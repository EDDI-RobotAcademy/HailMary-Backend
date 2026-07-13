from dataclasses import dataclass
from enum import Enum


class SajuCalendar(str, Enum):
    SOLAR = "solar"
    LUNAR = "lunar"


class SajuGender(str, Enum):
    MALE = "male"
    FEMALE = "female"


@dataclass(frozen=True)
class BirthProfile:
    """채팅 사주용 생년월일시 입력 (확인 모달에서 확정된 값).

    time_unknown=True면 시(時)를 모르는 케이스 — FortuneTeller에 'unknown' 전달.
    """

    birth_date: str  # "YYYY-MM-DD"
    birth_time: str | None  # "HH:MM" | None(모름)
    time_unknown: bool
    calendar: SajuCalendar
    gender: SajuGender

    def to_fortuneteller_payload(self) -> dict[str, str]:
        """FortuneTellerPort.analyze 입력 형식 (saju_data_extractor.extract와 동일 스키마)."""
        return {
            "birth": self.birth_date,
            "time": "unknown" if self.time_unknown or not self.birth_time else self.birth_time,
            "calendar": self.calendar.value,
            "gender": self.gender.value,
        }

    def cache_fingerprint(self) -> str:
        """캐시 키용 정규화 문자열 — 정확 일치 판정 기준 (해싱은 상위 레이어)."""
        t = "unknown" if self.time_unknown or not self.birth_time else self.birth_time
        return f"{self.birth_date}|{t}|{self.calendar.value}|{self.gender.value}"
