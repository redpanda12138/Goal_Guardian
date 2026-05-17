"""
One-off diagnostic script for MAS chat sessions.

What it checks:
- Stored session message_count vs actual non-deleted message rows
- Sessions with only 1 message
- Sessions with only assistant messages (no user messages)

Usage:
  python scripts/diagnose_mas_sessions.py
  python scripts/diagnose_mas_sessions.py --account-id user_xxx
  python scripts/diagnose_mas_sessions.py --limit 100
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from app.db import SessionLocal
from app.db.chat_entities import MessageEntity, MessageSessionEntity


def _session_summary(db, session: MessageSessionEntity) -> dict:
    rows = (
        db.query(MessageEntity)
        .filter_by(
            session_id=session.id,
            account_id=session.account_id,
            deleted=0,
        )
        .order_by(MessageEntity.sequence.asc(), MessageEntity.create_time.asc())
        .all()
    )

    user_count = sum(1 for r in rows if r.type == "ACCOUNT")
    assistant_count = sum(1 for r in rows if r.type == "SYSTEM")
    actual_count = len(rows)
    has_count_mismatch = int(session.message_count or 0) != actual_count

    return {
        "session_id": session.id,
        "account_id": session.account_id,
        "create_time": session.create_time.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(session.create_time, datetime)
        else str(session.create_time),
        "stored_message_count": int(session.message_count or 0),
        "actual_message_count": actual_count,
        "user_count": user_count,
        "assistant_count": assistant_count,
        "has_count_mismatch": has_count_mismatch,
        "is_single_message_session": actual_count == 1,
        "has_no_user_message": user_count == 0 and actual_count > 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose MAS session consistency")
    parser.add_argument("--account-id", dest="account_id", default=None, help="Filter by account_id")
    parser.add_argument("--limit", dest="limit", type=int, default=200, help="Max sessions to scan")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        q = db.query(MessageSessionEntity).filter_by(type="MAS").order_by(MessageSessionEntity.create_time.desc())
        if args.account_id:
            q = q.filter_by(account_id=args.account_id)
        sessions = q.limit(max(1, args.limit)).all()

        details = [_session_summary(db, s) for s in sessions]
        mismatches = [d for d in details if d["has_count_mismatch"]]
        single_msg = [d for d in details if d["is_single_message_session"]]
        no_user = [d for d in details if d["has_no_user_message"]]

        report = {
            "scanned_sessions": len(details),
            "count_mismatch_sessions": len(mismatches),
            "single_message_sessions": len(single_msg),
            "assistant_only_sessions": len(no_user),
            "details": details,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
