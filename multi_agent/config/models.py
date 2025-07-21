from datetime import datetime, time
from enum import Enum
from typing import Optional, Union, Any, Literal, Callable

from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic.main import IncEx


def int_to_time_str(val: int) -> str:
    if 0 <= val <= 23:
        return f"{val:02d}:00"
    raise ValueError("Hour integer must be between 0 and 23.")


class ParticipantPreferences(BaseModel):
    no_meetings_before: Optional[Union[str, int]] = Field(
        None, description="24-hour format string (e.g., '10:00') or int (e.g., 10)"
    )
    no_meetings_after: Optional[Union[str, int]] = Field(
        None, description="24-hour format string (e.g., '17:00') or int (e.g., 17)"
    )
    prefer_morning: Optional[bool] = Field(None, description="Prefers meetings between 06:00 and 12:00")
    prefer_afternoon: Optional[bool] = Field(None, description="Prefers meetings between 13:00 and 18:00")
    avoid_lunch_time: Optional[bool] = Field(None, description="Lunch hour is always 12:00–13:00")
    max_meetings_per_day: Optional[int] = Field(None, gt=0)
    preferred_max_duration: Optional[int] = Field(None, gt=0, description="Duration in minutes")

    def no_before(self) -> time:
        return time.fromisoformat(self.no_meetings_before)

    def no_after(self) -> time:
        return time.fromisoformat(self.no_meetings_after)

    @field_validator('no_meetings_before', 'no_meetings_after', mode='before')
    @classmethod
    def normalize_time(cls, v):
        if v is None:
            return v
        if isinstance(v, int):
            return int_to_time_str(v)
        if isinstance(v, str):
            import re
            if re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                return v
            if re.match(r'^([01]?[0-9]|2[0-3])$', v):
                return '0' + v if len(v) == 1 else v + ':00'
            raise ValueError('Time string must be in 24-hour format (HH:MM)')
        raise ValueError('Value must be int (0-23) or string in 24-hour format (HH:MM)')


class MeetingSchedule(BaseModel):
    schedule_day: datetime = Field(
        default_factory=datetime.now,
        description="Day of the meeting"
    )
    default_duration: int = Field(
        default=30, ge=15, le=480,
        description="Default meeting duration in minutes (15–480)."
    )
    working_hours_start: Union[int, str] = Field(
        default=8,
        description="Start of working hours as int (0–23) or string ('08:00')."
    )
    working_hours_end: Union[int, str] = Field(
        default=18,
        description="End of working hours as int (0–23) or string ('17:00')."
    )
    time_slot_interval: int = Field(
        default=30, ge=15, le=480,
        description="Interval between time slots in minutes (15–480)."
    )
    alternative_durations: list[int] = Field(
        default_factory=lambda: [15, 45, 60], min_length=1, max_length=5,
        description="List of alternative meeting durations in minutes (1–5 values)."
    )
    max_alternative_days: int = Field(
        default=3, ge=0, le=7,
        description="Maximum number of alternative days to suggest (0–7)."
    )

    def model_dump(
            self,
            *,
            mode: Literal['json', 'python'] | str = 'python',
            include: IncEx | None = None,
            exclude: IncEx | None = None,
            context: Any | None = None,
            by_alias: bool | None = None,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
            round_trip: bool = False,
            warnings: bool | Literal['none', 'warn', 'error'] = True,
            fallback: Callable[[Any], Any] | None = None,
            serialize_as_any: bool = False,
    ) -> dict[str, Any]:
        data = super().model_dump()
        data['schedule_day'] = self.schedule_day.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        return data

    @field_validator('schedule_day', mode='after')
    @classmethod
    def schedule_day_validator(cls, v):

        dt = datetime.now()

        if isinstance(v, str):
            dt = datetime.strptime(v, '%Y-%m-%d')

        if isinstance(v, datetime):
            dt = v

        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    @field_validator('working_hours_start', 'working_hours_end', mode='before')
    @classmethod
    def normalize_working_hours(cls, v):
        if isinstance(v, int):
            return int_to_time_str(v)
        if isinstance(v, str):
            import re
            if re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', v):
                return v
            raise ValueError('Time string must be in 24-hour format (HH:MM)')
        raise ValueError('Value must be int (0-23) or string in 24-hour format (HH:MM)')


class SlotInfo(BaseModel):
    start_time: str = Field(..., description="Start time in YYYY-MM-DD HH:MM format")
    end_time: str = Field(..., description="End time in YYYY-MM-DD HH:MM format")
    duration_minutes: int = Field(..., gt=0, description="Duration in minutes")
    confidence: float = Field(default=0, ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    participants: list[str] = Field(..., description="List of participant identifiers")
    participant_scores: list[float] = Field(..., description="Mapping of participant to their score")
    participant_notes: dict[str, list[str]] = Field(..., description="Mapping of participant to their notes")
    notes: str = Field(..., description="Generated notes for the slot")
    day_of_week: str = Field(..., description="Day of the week (e.g., Monday)")
    score: float = Field(default=0.0, description="Average score for the slot")


class NegotiationOutcome(str, Enum):
    OPTIMAL_FOUND = "optimal_found"
    COMPROMISE_PROPOSED = "compromise_proposed"
    IMPOSSIBLE = "impossible"

class NegotiationStrategy(int, Enum):
    NONE=0
    DURATION_ADJUSTMENT = 1
    TOD_SHIFTING = 2
    ALTERNATIVE_DAY = 3
    RELAX_CONSTRAINTS = 4


class NegotiationResult(BaseModel):
    outcome: NegotiationOutcome = Field(NegotiationOutcome.IMPOSSIBLE)
    proposed_schedule: Optional[MeetingSchedule] = Field(None, description="Meeting schedule.")
    selected_slot: Optional[SlotInfo] = Field(None, description="Selected slot.")
    reasoning: str = Field(..., description="Reasoning")
    alternative_suggestions: list[SlotInfo] = Field(default_factory=list, description="Alternative suggestions.")
    strategy_choose: NegotiationStrategy = Field(NegotiationStrategy.NONE, description='Strategy choose in negotiation')

    model_config = ConfigDict(use_enum_values=True)
