from datetime import datetime, timedelta
from typing import Optional


MAS_SESSION_CREATE_DEDUPE_SECONDS = 60


def is_recent_session(
    create_time: Optional[datetime],
    *,
    now: Optional[datetime] = None,
    window_seconds: int = MAS_SESSION_CREATE_DEDUPE_SECONDS,
) -> bool:
    if create_time is None:
        return False
    current_time = now or datetime.now(tz=create_time.tzinfo)
    age = current_time - create_time
    return timedelta(0) <= age <= timedelta(seconds=window_seconds)
