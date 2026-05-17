import unittest

from note_utils import prepare_note_for_extraction


class TestPrepareNoteForExtraction(unittest.TestCase):
    def test_chat_transcript_is_converted_to_client_summary_lines(self):
        raw_note = (
            "Assistant: Hi there! How are you today?\n"
            "User: I feel better than last week.\n"
            "Assistant: Great to hear. Anything else?\n"
            "User: I walked 30 minutes on Monday and Thursday.\n"
        )

        prepared = prepare_note_for_extraction(raw_note)

        self.assertEqual(
            prepared,
            "Client summary:\n"
            "- I feel better than last week.\n"
            "\n"
            "Goals setting:\n"
            "1. I walked 30 minutes on Monday and Thursday.",
        )

    def test_chat_transcript_with_feedback_creates_feedback_section(self):
        raw_note = (
            "Assistant: Any feedback for this session?\n"
            "User: Please add voice input function.\n"
            "User: I feel more energetic this week.\n"
        )

        prepared = prepare_note_for_extraction(raw_note)

        self.assertEqual(
            prepared,
            "Client summary:\n"
            "- I feel more energetic this week.\n"
            "\n"
            "Feedback:\n"
            "- Please add voice input function.",
        )

    def test_non_transcript_note_keeps_original_information(self):
        raw_note = (
            "Client, Daniel, returned from Penang.\n\n"
            "Goals setting:\n"
            "1. Walk 30 minutes twice a week.\n"
        )

        prepared = prepare_note_for_extraction(raw_note)

        self.assertEqual(
            prepared,
            "Client, Daniel, returned from Penang.\n"
            "Goals setting:\n"
            "1. Walk 30 minutes twice a week.",
        )


if __name__ == "__main__":
    unittest.main()
