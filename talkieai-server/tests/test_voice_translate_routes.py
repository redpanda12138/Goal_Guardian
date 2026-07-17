import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SQL_ECHO", "false")
os.environ.setdefault("TOKEN_EXPIRE_TIME", "3600")


class VoiceTranslateRoutesTest(unittest.TestCase):
    @patch.dict(
        os.environ,
        {
            "DATABASE_URL": "sqlite:///:memory:",
            "SQL_ECHO": "false",
            "TOKEN_EXPIRE_TIME": "3600",
        },
    )
    def test_standalone_voice_translate_lazily_uses_whisper_processor(self):
        from app.api import session_routes

        fake_whisper = types.ModuleType("app.core.whisper_voice")
        fake_whisper.whisper_processor = SimpleNamespace(
            processor=object(),
            model=object(),
            pipe=None,
            transcribe_audio=lambda _: "recognized text",
        )

        with tempfile.NamedTemporaryFile(suffix=".wav") as audio_file:
            audio_file.write(b"fake-audio")
            audio_file.flush()

            with patch.dict(sys.modules, {"app.core.whisper_voice": fake_whisper}):
                with patch.object(session_routes, "voice_file_get_path", return_value=audio_file.name):
                    with patch.object(session_routes, "validate_audio_file", return_value=True):
                        response = session_routes.standalone_voice_translate_api(
                            SimpleNamespace(file_name="recording.wav"),
                            db=None,
                            account_id="account_1",
                        )

        self.assertEqual(response.data["transcribed_text"], "recognized text")
        self.assertEqual(response.data["original_file"], "recording.wav")


if __name__ == "__main__":
    unittest.main()
