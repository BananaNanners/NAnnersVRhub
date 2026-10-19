"""24-hour local presentation. Stored timestamps and the OS timezone are untouched."""
from datetime import datetime, timezone
import re


def _parse(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None
    except ValueError:
        return None


def local_time(value):
    stamp = _parse(value)
    if stamp is None:
        return "unknown (timestamp not recorded)" if not value else "unknown (invalid timestamp)"
    if stamp.utcoffset() is None:
        return stamp.strftime("%Y-%m-%d %H:%M:%S") + " (timezone not recorded)"
    return stamp.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def age_text(value, now=None):
    stamp = _parse(value)
    if stamp is None or stamp.utcoffset() is None:
        return "age unknown"
    seconds = ((now or datetime.now(timezone.utc)) - stamp).total_seconds()
    if seconds < -5:
        return "timestamp is in the future"
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s old"
    minutes, seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s old"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m old"


def filename_stamp(value):
    stamp = _parse(value)
    if stamp is None or stamp.utcoffset() is None:
        return "undated"
    return re.sub(r"[^A-Za-z0-9_-]", "_", stamp.astimezone().strftime("%Y-%m-%d_%H-%M-%S_%Z"))
