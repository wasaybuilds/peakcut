"""Posting queue: a few fixed times a day (laptop's local clock), one clip per time slot.

The times live in data/schedule.json. A queued clip gets the next free slot and one pending
Publish row per platform, all with that slot's `scheduled_at` (aware UTC, which is what SQLModel
stores and hands back). The publisher thread posts rows when their time comes.
"""

import json
import re
from datetime import UTC, datetime, timedelta

from app.config import get_settings

DEFAULT_TIMES = ["12:00", "17:00", "21:00"]
MAX_TIMES = 8
LEAD = timedelta(minutes=2)  # never hand out a slot that starts in less than this
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.utcoffset() is None else dt.astimezone(UTC)


def iso(dt: datetime | None) -> str | None:
    """ISO string with an explicit offset, so browsers don't read it as local time."""
    return _utc(dt).isoformat() if dt else None


def _path():
    return get_settings().data_dir / "schedule.json"


def get_times() -> list[str]:
    try:
        times = json.loads(_path().read_text(encoding="utf-8")).get("times")
        return normalise(times)
    except (OSError, ValueError, TypeError):
        return list(DEFAULT_TIMES)


def normalise(times) -> list[str]:
    if not isinstance(times, list):
        raise ValueError("times must be a list")
    out = sorted({t.strip() for t in times if isinstance(t, str)})
    if not out or len(out) > MAX_TIMES or not all(_TIME.match(t) for t in out):
        raise ValueError(f"Use 1 to {MAX_TIMES} times written as HH:MM, for example 17:00.")
    return out


def set_times(times: list[str]) -> list[str]:
    out = normalise(times)
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps({"times": out}), encoding="utf-8")
    return out


def slots_after(after: datetime, times: list[str] | None = None):
    """Slot start times (aware UTC) strictly after `after`, in order, forever."""
    times = times or get_times()
    after = _utc(after)
    local_after = after.astimezone()  # laptop's time zone
    day = local_after.date()
    while True:
        for t in times:
            h, m = map(int, t.split(":"))
            local = datetime(day.year, day.month, day.day, h, m).astimezone()
            slot = local.astimezone(UTC)
            if slot > after:
                yield slot
        day += timedelta(days=1)


def next_free_slot(taken: set[datetime], now: datetime | None = None, times: list[str] | None = None) -> datetime:
    now = _utc(now) if now else utcnow()
    taken = {_utc(t) for t in taken}
    for slot in slots_after(now + LEAD, times):
        if slot not in taken:
            return slot
    raise RuntimeError("unreachable")
