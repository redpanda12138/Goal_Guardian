from goal_titles import (
    build_goal_title_map,
    fallback_goal_title,
    titles_for_goals,
)


def test_ai_titles_are_normalized_to_a_few_words():
    goals = ["Walk 30 minutes three times this week"]
    title_map = build_goal_title_map(
        goals,
        ["Consistent Weekly Walking Routine for Better Health"],
    )

    assert title_map == {
        "walk 30 minutes three times this week": "Consistent Weekly Walking Routine"
    }


def test_goal_titles_prefer_ai_output_and_fall_back_for_legacy_data():
    goals = [
        "Walk 30 minutes three times this week",
        "Stretch for 10 minutes every day",
    ]
    title_map = {
        "walk 30 minutes three times this week": "Weekly Walking Routine"
    }

    assert titles_for_goals(goals, title_map) == [
        "Weekly Walking Routine",
        "Daily Stretching",
    ]


def test_fallback_title_never_repeats_the_full_goal_sentence():
    goal = "Practice tennis with a friend for one hour on Saturday morning"

    title = fallback_goal_title(goal)

    assert title == "Saturday Tennis Practice"
    assert len(title.split()) <= 5
