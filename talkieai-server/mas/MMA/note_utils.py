import re
from typing import List, Tuple
from datetime import datetime


def _normalize_lines(raw_note: str) -> List[str]:
    if not raw_note:
        return []
    return [line.strip() for line in str(raw_note).split("\n") if line.strip()]


def _extract_role_and_content(line: str) -> Tuple[str, str]:
    if ":" not in line:
        return "", line
    role, content = line.split(":", 1)
    return role.strip().lower(), content.strip()


def prepare_note_for_extraction(raw_note: str) -> str:
    """
    Prepare text for extraction.

    - For chat transcript style notes (Assistant/User lines), keep only patient utterances
      and normalize them as `Client: <content>`.
    - For regular coaching notes, keep normalized original text.
    """
    lines = _normalize_lines(raw_note)
    if not lines:
        return ""

    known_roles = {"assistant", "user", "client", "patient", "coach", "health coach"}
    patient_roles = {"user", "client", "patient"}

    saw_dialogue_prefix = False
    patient_contents: List[str] = []

    for line in lines:
        role, content = _extract_role_and_content(line)
        if role in known_roles:
            saw_dialogue_prefix = True
            if role in patient_roles and content:
                patient_contents.append(content)

    if saw_dialogue_prefix and patient_contents:
        goal_pattern = re.compile(
            r"\b(goal|goals|next week|will|walk|run|exercise|steps|minutes|times|practice|attend|add|eat)\b",
            flags=re.IGNORECASE,
        )
        feedback_pattern = re.compile(
            r"\b(feedback|suggest|improve|function|feature|voice input)\b",
            flags=re.IGNORECASE,
        )

        feedback_items = [x for x in patient_contents if feedback_pattern.search(x)]
        goal_items = [x for x in patient_contents if goal_pattern.search(x) and x not in feedback_items]

        summary_items = [x for x in patient_contents if x not in goal_items and x not in feedback_items]
        if not summary_items:
            summary_items = patient_contents[:]

        lines: List[str] = ["Client summary:"]
        for item in summary_items[:3]:
            lines.append(f"- {item}")

        if goal_items:
            lines.append("")
            lines.append("Goals setting:")
            for idx, item in enumerate(goal_items[:3], start=1):
                lines.append(f"{idx}. {item}")

        if feedback_items:
            lines.append("")
            lines.append("Feedback:")
            for item in feedback_items[:2]:
                lines.append(f"- {item}")

        return "\n".join(lines)

    return "\n".join(lines)


def _semantic_key(text: str) -> str:
    """Build a loose semantic key for phrase-level deduplication."""
    s = str(text or "").strip().lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(i\s+)?(like|love|enjoy)\s+", "", s)
    s = re.sub(r"^(to\s+)?(play|playing|do|doing|go|going|attend|attending)\s+", "", s)
    s = re.sub(r"^(to\s+the\s+|to\s+|the\s+)", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def merge_semantic_items(existing: List[str], incoming: List[str]) -> List[str]:
    """
    Merge phrase lists with semantic deduplication.

    Example:
    - "badminton" and "playing badminton" -> keep one concise entry.
    """
    merged: dict[str, str] = {}

    def pick_better(current: str, candidate: str) -> str:
        current_score = (len(current.split()), len(current))
        candidate_score = (len(candidate.split()), len(candidate))
        return candidate if candidate_score < current_score else current

    for item in list(existing or []) + list(incoming or []):
        value = str(item or "").strip()
        if not value:
            continue
        key = _semantic_key(value)
        if not key:
            continue
        if key in merged:
            merged[key] = pick_better(merged[key], value)
        else:
            merged[key] = value

    # Stable output for reproducibility
    return sorted(merged.values(), key=lambda x: x.lower())


def build_latest_goals_index(goal_entries: List[dict]) -> dict:
    """
    Build patient_id -> latest goal entry index from historical entries.
    """
    latest: dict[str, dict] = {}

    for entry in goal_entries or []:
        patient_id = str(entry.get("patient_id") or "").strip()
        date_str = str(entry.get("date") or "").strip()
        if not patient_id or not date_str:
            continue
        try:
            current_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        existing = latest.get(patient_id)
        if not existing:
            latest[patient_id] = entry
            continue

        try:
            existing_date = datetime.strptime(existing.get("date", ""), "%Y-%m-%d")
        except ValueError:
            latest[patient_id] = entry
            continue

        if current_date >= existing_date:
            latest[patient_id] = entry

    return latest


def get_patient_goal_history(goal_entries: List[dict], patient_id: str) -> List[dict]:
    """
    Return all goal entries for one patient, sorted by date descending.
    Invalid-date entries are kept at the end in original relative order.
    """
    target = str(patient_id or "").strip()
    filtered = [e for e in (goal_entries or []) if str(e.get("patient_id", "")).strip() == target]

    valid_entries: List[tuple[datetime, dict]] = []
    invalid_entries: List[dict] = []
    for entry in filtered:
        try:
            parsed = datetime.strptime(str(entry.get("date", "")).strip(), "%Y-%m-%d")
            valid_entries.append((parsed, entry))
        except ValueError:
            invalid_entries.append(entry)

    valid_entries.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in valid_entries] + invalid_entries


def apply_history_limit(history: List[dict], limit: int | None) -> List[dict]:
    """Apply optional top-N limit to history list."""
    if limit is None:
        return history
    return history[:limit]


def apply_history_pagination(
    history: List[dict],
    offset: int = 0,
    limit: int | None = None,
) -> List[dict]:
    """Apply offset + optional limit to history list."""
    page = history[offset:] if offset > 0 else history
    return apply_history_limit(page, limit)
