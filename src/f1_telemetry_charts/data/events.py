"""Event and session discovery for user-facing session selection."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field

from f1_telemetry_charts.data.gateways.base import DataGatewayError


class AvailableSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    session_type: str
    starts_at: datetime | None = None


class EventSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    round_number: int | None = Field(default=None, ge=0)
    event_name: str
    official_name: str | None = None
    country: str | None = None
    location: str | None = None
    event_date: date | None = None
    event_format: str | None = None
    sessions: list[AvailableSession] = Field(default_factory=list)


class SeasonEventSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    season: int = Field(ge=1950)
    events: list[EventSummary] = Field(default_factory=list)


class EventCatalog(Protocol):
    def events_for_season(self, season: int) -> SeasonEventSchedule: ...


class FastF1EventCatalog:
    """Read official event schedules through FastF1 without loading session data."""

    def __init__(self, schedule_loader: Callable[[int], Any] | None = None):
        self._schedule_loader = schedule_loader

    def events_for_season(self, season: int) -> SeasonEventSchedule:
        loader = self._schedule_loader
        if loader is None:
            try:
                import fastf1
            except ImportError as exc:
                raise DataGatewayError(
                    "FastF1 is not installed, so the event schedule is unavailable."
                ) from exc
            loader = lambda year: fastf1.get_event_schedule(  # noqa: E731
                year, include_testing=False
            )
        try:
            schedule = loader(season)
        except Exception as exc:
            raise DataGatewayError(
                f"FastF1 could not load the {season} event schedule: {exc}"
            ) from exc
        return season_schedule_from_rows(season, schedule)


class FixtureEventCatalog:
    """Deterministic in-memory catalog for tests and offline UI fixtures."""

    def __init__(self, schedules: list[SeasonEventSchedule | dict[str, Any]]):
        self._schedules = {
            schedule.season: schedule
            for schedule in (
                SeasonEventSchedule.model_validate(item) for item in schedules
            )
        }

    def events_for_season(self, season: int) -> SeasonEventSchedule:
        return self._schedules.get(season, SeasonEventSchedule(season=season))


def season_schedule_from_rows(season: int, schedule: Any) -> SeasonEventSchedule:
    """Normalize a pandas-like FastF1 schedule into stable API models."""

    events: list[EventSummary] = []
    for _, row in schedule.iterrows():
        event_name = _text(row.get("EventName"))
        if event_name is None:
            continue
        sessions = []
        for index in range(1, 6):
            name = _text(row.get(f"Session{index}"))
            if name is None:
                continue
            sessions.append(
                AvailableSession(
                    name=name,
                    session_type=normalize_session_type(name),
                    starts_at=_datetime(row.get(f"Session{index}DateUtc"))
                    or _datetime(row.get(f"Session{index}Date")),
                )
            )
        event_datetime = _datetime(row.get("EventDate"))
        events.append(
            EventSummary(
                round_number=_integer(row.get("RoundNumber")),
                event_name=event_name,
                official_name=_text(row.get("OfficialEventName")),
                country=_text(row.get("Country")),
                location=_text(row.get("Location")),
                event_date=event_datetime.date() if event_datetime else None,
                event_format=_text(row.get("EventFormat")),
                sessions=sessions,
            )
        )
    events.sort(key=lambda event: (event.event_date or date.max, event.round_number or 999))
    return SeasonEventSchedule(season=season, events=events)


def normalize_session_type(name: str) -> str:
    value = " ".join(name.strip().lower().replace("_", " ").split())
    if value in {"fp1", "fp2", "fp3"} or value.startswith("practice"):
        return "practice"
    if "sprint" in value and any(
        token in value for token in ("qualifying", "shootout", "qualification")
    ):
        return "sprint_qualifying"
    if value in {"q", "qualifying", "qualification"}:
        return "qualifying"
    if "sprint" in value:
        return "sprint"
    if value in {"r", "race"}:
        return "race"
    return "other"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text.lower() in {"nan", "nat", "none"} else text


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    converter = getattr(value, "to_pydatetime", None)
    if callable(converter):
        try:
            converted = converter()
            return converted if isinstance(converted, datetime) else None
        except (TypeError, ValueError, OverflowError):
            return None
    text = _text(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
