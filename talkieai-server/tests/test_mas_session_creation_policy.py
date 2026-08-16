from datetime import datetime, timedelta
from pathlib import Path

from app.services.mas.session_creation_policy import is_recent_session


def test_recent_session_is_reusable_inside_deduplication_window():
    now = datetime(2026, 8, 16, 12, 0, 0)

    assert is_recent_session(now - timedelta(seconds=30), now=now)
    assert not is_recent_session(now - timedelta(seconds=61), now=now)


def test_missing_creation_time_is_not_reusable():
    assert not is_recent_session(None)


def test_chat_service_reuses_recent_mas_session_before_resetting_oa():
    server_root = Path(__file__).resolve().parents[1]
    source = (server_root / "app" / "services" / "chat_service.py").read_text(
        encoding="utf-8"
    )
    method_source = source.split("def create_mas_session", 1)[1].split(
        "def get_or_create_mas_session", 1
    )[0]

    reuse_position = method_source.index("if recent_session and is_recent_session")
    create_position = method_source.index("self.create_session")
    reset_position = method_source.index("reset_session")
    assert reuse_position < create_position < reset_position
