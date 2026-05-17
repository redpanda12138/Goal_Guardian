import unittest

from note_utils import build_latest_goals_index


class TestLatestGoalsIndex(unittest.TestCase):
    def test_keeps_latest_entry_per_patient(self):
        entries = [
            {
                "patient_id": "patient_1",
                "date": "2025-07-01",
                "output": {"goals": ["goal old"]},
            },
            {
                "patient_id": "patient_1",
                "date": "2025-07-15",
                "output": {"goals": ["goal new"]},
            },
            {
                "patient_id": "patient_2",
                "date": "2025-06-20",
                "output": {"goals": ["goal p2"]},
            },
        ]

        latest = build_latest_goals_index(entries)

        self.assertEqual(latest["patient_1"]["output"]["goals"], ["goal new"])
        self.assertEqual(latest["patient_2"]["output"]["goals"], ["goal p2"])

    def test_skips_invalid_dates(self):
        entries = [
            {"patient_id": "patient_1", "date": "bad-date", "output": {"goals": ["x"]}},
            {"patient_id": "patient_1", "date": "2025-07-10", "output": {"goals": ["y"]}},
        ]

        latest = build_latest_goals_index(entries)

        self.assertEqual(latest["patient_1"]["output"]["goals"], ["y"])


if __name__ == "__main__":
    unittest.main()
