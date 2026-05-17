import unittest

from note_utils import merge_semantic_items


class TestSemanticDedup(unittest.TestCase):
    def test_hobby_phrase_variants_are_merged(self):
        existing = ["badminton", "fitness club"]
        incoming = ["playing badminton", "going to the fitness club", "badminton"]

        merged = merge_semantic_items(existing, incoming)

        self.assertIn("badminton", merged)
        self.assertIn("fitness club", merged)
        self.assertNotIn("playing badminton", merged)
        self.assertNotIn("going to the fitness club", merged)

    def test_non_equivalent_items_are_kept(self):
        existing = ["reading detective novels"]
        incoming = ["knitting", "book club"]

        merged = merge_semantic_items(existing, incoming)

        self.assertEqual(
            merged,
            ["book club", "knitting", "reading detective novels"],
        )


if __name__ == "__main__":
    unittest.main()
