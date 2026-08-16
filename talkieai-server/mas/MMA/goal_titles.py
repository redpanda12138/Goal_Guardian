import re
from typing import Dict, Iterable, List, Optional


MAX_TITLE_WORDS = 5


def normalize_goal_key(goal: str) -> str:
    return str(goal or "").strip().rstrip(".,;:!?").lower()


def _clean_title(title: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", str(title or ""))
    words = words[:MAX_TITLE_WORDS]
    while words and words[-1].lower() in {"and", "for", "of", "the", "to", "with"}:
        words.pop()
    return " ".join(words).strip()


def fallback_goal_title(goal: str) -> str:
    lowered = normalize_goal_key(goal)
    day = next(
        (
            value.title()
            for value in (
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            )
            if value in lowered
        ),
        "",
    )
    cadence = "Daily" if re.search(r"\b(daily|every day)\b", lowered) else "Weekly"

    activities = (
        (("tennis", "badminton", "sport"), "Tennis Practice"),
        (("walk", "steps", "jog"), "Walking Routine"),
        (("stretch", "yoga"), "Stretching"),
        (("run", "treadmill", "cardio"), "Running"),
        (("swim", "pool"), "Swimming"),
        (("gym", "exercise", "fitness"), "Exercise Plan"),
    )
    for keywords, label in activities:
        if any(keyword in lowered for keyword in keywords):
            return f"{day or cadence} {label}"

    meaningful = [
        word
        for word in re.findall(r"[A-Za-z]+", goal)
        if word.lower()
        not in {
            "a",
            "an",
            "and",
            "for",
            "in",
            "of",
            "on",
            "the",
            "this",
            "to",
            "with",
        }
    ]
    if meaningful:
        return " ".join(word.title() for word in meaningful[:4])
    return "Weekly Activity Plan"


def sanitize_goal_title(title: str, goal: str) -> str:
    cleaned = _clean_title(title)
    if len(cleaned.split()) < 2:
        return fallback_goal_title(goal)
    return cleaned


def build_goal_title_map(
    goals: Iterable[str], raw_titles: Optional[Iterable[str]] = None
) -> Dict[str, str]:
    goal_list = [str(goal or "").strip() for goal in goals]
    title_list = list(raw_titles or [])
    return {
        normalize_goal_key(goal): sanitize_goal_title(
            title_list[index] if index < len(title_list) else "", goal
        )
        for index, goal in enumerate(goal_list)
        if normalize_goal_key(goal)
    }


def titles_for_goals(goals: Iterable[str], title_map: Optional[dict]) -> List[str]:
    stored = title_map if isinstance(title_map, dict) else {}
    return [
        sanitize_goal_title(stored.get(normalize_goal_key(goal), ""), goal)
        for goal in goals
    ]
