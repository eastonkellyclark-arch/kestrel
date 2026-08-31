"""Timestamp normalisation.

Every source states its dates differently. The translator used to handle this
with `posted_at[:19]` — take the first 19 characters and hope. That works for
ISO 8601 and silently corrupts anything else:

    "2026-08-12T18:00:00Z"           -> "2026-08-12T18:00:00"   ok
    "Wed, 12 Aug 2026 18:00:00 +0000" -> "Wed, 12 Aug 2026 18"  garbage

The garbage then fails `datetime.fromisoformat` in the freshness scorer, which
falls back to 40/100 ("no date"). We Work Remotely listings were scoring as
undated rather than fresh — a silent ~9 point loss on every one of them.

Everything goes through `normalize_timestamp` now, which understands the
formats our sources actually emit, converts to UTC, and returns a string that
`datetime.fromisoformat` can always read. Anything genuinely unparseable
returns "" — an explicit "no date", which the scorer already handles — rather
than a truncated string that looks like a date and is not.
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Sources have posted things dated 1970 and 2100; both are wrong. Bracketing
# the plausible range stops an epoch-parsed-as-seconds/millis mixup from
# silently producing a date centuries out.
_MIN_YEAR = 1990
_MAX_YEAR = 2100


def _to_utc_string(dt: datetime) -> str:
    """Render a datetime as a naive UTC ISO string (what the DB and scorers use)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0).isoformat()


def _from_epoch(value: float) -> datetime | None:
    # Heuristic: anything past ~2001 in seconds is milliseconds.
    if value > 1e11:
        value = value / 1000.0
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def normalize_timestamp(value: object) -> str:
    """Return a naive-UTC ISO 8601 string, or "" if the value is not a date.

    Accepts ISO 8601 (with or without offset or trailing Z), RFC 822/2822 as
    used by RSS, epoch seconds, epoch milliseconds, and datetime objects.
    """
    if value is None:
        return ""

    if isinstance(value, datetime):
        return _to_utc_string(value)

    # Numeric epochs, as numbers or as digit strings.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        dt = _from_epoch(float(value))
        return _to_utc_string(dt) if dt and _MIN_YEAR <= dt.year <= _MAX_YEAR else ""

    if not isinstance(value, str):
        return ""

    text = value.strip()
    if not text:
        return ""

    if text.isdigit():
        dt = _from_epoch(float(text))
        return _to_utc_string(dt) if dt and _MIN_YEAR <= dt.year <= _MAX_YEAR else ""

    # ISO 8601. fromisoformat handles offsets; it does not handle a trailing Z
    # before 3.11, and does not like sub-second precision beyond 6 digits
    # (USAJobs sends 7).
    iso = text.replace("Z", "+00:00") if text.endswith("Z") else text
    for candidate in (iso, iso[:26], iso[:19]):
        try:
            dt = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if _MIN_YEAR <= dt.year <= _MAX_YEAR:
            return _to_utc_string(dt)

    # RFC 822 / 2822, as used by RSS pubDate.
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        dt = None
    if dt is not None and _MIN_YEAR <= dt.year <= _MAX_YEAR:
        return _to_utc_string(dt)

    return ""
