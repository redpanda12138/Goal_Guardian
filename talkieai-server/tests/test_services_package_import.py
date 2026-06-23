import os
import subprocess
import sys
import unittest
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]


class ServicesPackageImportTest(unittest.TestCase):
    def run_import_check(self, command):
        env = os.environ.copy()
        env["DATABASE_URL"] = "sqlite:///:memory:"
        env["SQL_ECHO"] = "false"
        try:
            return subprocess.run(
                [sys.executable, "-c", command],
                cwd=SERVER_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail("import exceeded 30 seconds: {}".format(exc))

    def test_import_does_not_eagerly_load_chat_or_torch(self):
        command = (
            "import sys; import app.services; "
            "assert 'app.services.chat_service' not in sys.modules; "
            "assert 'torch' not in sys.modules"
        )
        result = self.run_import_check(command)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ai_package_does_not_eagerly_load_provider_sdks(self):
        command = (
            "import sys; import app.ai; "
            "assert 'app.ai.impl.zhipu_ai' not in sys.modules; "
            "assert 'app.ai.impl.chat_gpt_ai' not in sys.modules; "
            "assert 'zhipuai' not in sys.modules; "
            "assert 'openai' not in sys.modules"
        )
        result = self.run_import_check(command)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_chat_service_import_does_not_load_whisper_or_torch(self):
        command = (
            "import sys; import app.services.chat_service; "
            "assert 'app.core.whisper_voice' not in sys.modules; "
            "assert 'torch' not in sys.modules"
        )
        result = self.run_import_check(command)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_session_routes_import_does_not_load_whisper_or_torch(self):
        command = (
            "import sys; import app.api.session_routes; "
            "assert 'app.core.whisper_voice' not in sys.modules; "
            "assert 'torch' not in sys.modules"
        )
        result = self.run_import_check(command)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
