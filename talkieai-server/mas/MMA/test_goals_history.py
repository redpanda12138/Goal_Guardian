import unittest

from note_utils import get_patient_goal_history, apply_history_limit, apply_history_pagination


class TestGoalsHistory(unittest.TestCase):
    def test_returns_patient_history_desc_by_date(self):
        entries = [
            {"patient_id": "p1", "date": "2025-07-01", "output": {"goals": ["g1"]}},
            {"patient_id": "p1", "date": "2025-07-10", "output": {"goals": ["g2"]}},
            {"patient_id": "p2", "date": "2025-07-05", "output": {"goals": ["x"]}},
            {"patient_id": "p1", "date": "2025-06-01", "output": {"goals": ["g0"]}},
        ]

        history = get_patient_goal_history(entries, "p1")

        self.assertEqual(
            [row["date"] for row in history],
            ["2025-07-10", "2025-07-01", "2025-06-01"],
        )

    def test_keeps_invalid_date_entries_at_end(self):
        entries = [
            {"patient_id": "p1", "date": "bad-date", "output": {"goals": ["g_bad"]}},
            {"patient_id": "p1", "date": "2025-07-01", "output": {"goals": ["g1"]}},
        ]

        history = get_patient_goal_history(entries, "p1")

        self.assertEqual(history[0]["date"], "2025-07-01")
        self.assertEqual(history[1]["date"], "bad-date")

    def test_history_limit_applies_top_n(self):
        history = [
            {"date": "2025-07-10"},
            {"date": "2025-07-01"},
            {"date": "2025-06-01"},
        ]

        limited = apply_history_limit(history, 2)

        self.assertEqual(len(limited), 2)
        self.assertEqual([row["date"] for row in limited], ["2025-07-10", "2025-07-01"])

    def test_history_pagination_with_offset_and_limit(self):
        history = [
            {"date": "2025-07-10"},
            {"date": "2025-07-01"},
            {"date": "2025-06-01"},
            {"date": "2025-05-01"},
        ]

        paged = apply_history_pagination(history, offset=1, limit=2)

        self.assertEqual(
            [row["date"] for row in paged],
            ["2025-07-01", "2025-06-01"],
        )


if __name__ == "__main__":
    unittest.main()
