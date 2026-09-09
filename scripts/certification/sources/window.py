"""Strict, shared UTC window contract, validated before source I/O."""
from datetime import datetime, timezone


def validate_window(start, end):
    def canonical(value):
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
            if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
                raise ValueError('invalid_window')
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError('invalid_window') from exc

    start, end = canonical(start), canonical(end)
    if start >= end:
        raise ValueError('invalid_window')
    return start, end
