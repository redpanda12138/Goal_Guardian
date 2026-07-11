import unittest
import sys
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]
COMMON_ROOT = SERVER_ROOT / "mas" / "common"
for path in (SERVER_ROOT, COMMON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from prompt_guard import build_coach_prompt, safe_coach_reply  # noqa: E402


class MasPromptGuardTest(unittest.TestCase):
    def test_safe_coach_reply_replaces_prompt_leak(self):
        fallback = "Thanks for sharing. Could you tell me a little more about that?"

        reply = safe_coach_reply(
            "The client said: 'I feel good'. Reflect empathetically and ask for a positive health moment.",
            fallback,
        )

        self.assertEqual(reply, fallback)

    def test_build_coach_prompt_requests_only_user_visible_reply(self):
        prompt = build_coach_prompt(
            "I feel good today.",
            "Reflect empathetically and ask one short follow-up.",
        )

        self.assertIn("Return only the exact message", prompt)
        self.assertIn("Client message: I feel good today.", prompt)
        self.assertIn("Task: Reflect empathetically", prompt)


if __name__ == "__main__":
    unittest.main()
