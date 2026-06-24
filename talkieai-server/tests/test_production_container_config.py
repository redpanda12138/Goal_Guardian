import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAS_SERVICES = ("mma", "soa", "gra", "sca", "ssa", "oa")


class ProductionContainerConfigTest(unittest.TestCase):
    def read(self, relative_path):
        path = ROOT / relative_path
        self.assertTrue(path.is_file(), f"missing deployment file: {relative_path}")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def service_block(compose, service):
        match = re.search(
            rf"(?ms)^  {service}:\r?\n(.*?)(?=^  [a-z][a-z0-9-]*:\r?\n|^networks:|^volumes:|\Z)",
            compose,
        )
        if not match:
            raise AssertionError(f"missing Compose service: {service}")
        return match.group(1)

    def test_backend_dockerfile_runs_uvicorn_in_foreground(self):
        dockerfile = self.read("talkieai-server/Dockerfile")
        self.assertIn("FROM python:3.10-slim", dockerfile)
        self.assertIn("ffmpeg", dockerfile)
        self.assertIn("libsndfile1", dockerfile)
        self.assertIn("libgomp1", dockerfile)
        self.assertIn("pip install --no-cache-dir -r requirements.txt", dockerfile)
        self.assertIn(
            'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8098"]',
            dockerfile,
        )

    def test_docker_context_excludes_secrets_models_and_runtime_files(self):
        dockerignore = self.read("talkieai-server/.dockerignore")
        for entry in (
            ".env",
            ".env.production",
            "myenv/",
            "files/",
            "uploads/",
            "mas/whisper-medium-sing2eng-translate/",
            "mas/whisper-model-offline/",
        ):
            self.assertIn(entry, dockerignore)

        gitignore = self.read(".gitignore")
        self.assertIn("/talkieai-server/.env.production", gitignore)

    def test_production_environment_example_is_safe_and_complete(self):
        env_example = self.read("talkieai-server/.env.production.example")
        for setting in (
            "DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@HOST/",
            "TOKEN_SECRET=replace-with-random-256-bit-secret",
            "ZHIPU_AI_API_KEY=replace-with-rotated-production-key",
            "MAS_MEMORY_REQUIRE_DATABASE=true",
            "TEMP_SAVE_FILE_PATH=/app/files",
            "WHISPER_MODEL_PATH=/models/whisper",
        ):
            self.assertIn(setting, env_example)
        self.assertNotRegex(env_example, r"(?i)(sk-[a-z0-9]{20,}|[a-f0-9]{32}\.[a-z0-9]{10,})")

    def test_cpu_compose_uses_private_healthy_mas_services(self):
        compose = self.read("docker-compose.prod.yml")
        self.assertEqual(compose.count("restart: unless-stopped"), 7)
        self.assertEqual(compose.count("healthcheck:"), 7)
        self.assertEqual(compose.count("condition: service_healthy"), 6)
        self.assertIn('"127.0.0.1:8098:8098"', self.service_block(compose, "backend"))

        for service in MAS_SERVICES:
            block = self.service_block(compose, service)
            self.assertNotIn("ports:", block)
            self.assertIn("entrypoint: []", block)
            self.assertIn("uvicorn app:app", block)
            self.assertIn("./talkieai-server/mas/common:/app/common:ro", block)
            self.assertIn(f"MAS_{service.upper()}_URL: http://{service}:8000", compose)

        self.assertIn("MAS_MEMORY_REQUIRE_DATABASE: \"true\"", compose)
        self.assertIn("backend-files:/app/files", compose)
        self.assertIn("/models/whisper:ro", compose)

    def test_gpu_override_only_requests_a_device_for_backend(self):
        gpu = self.read("docker-compose.gpu.yml")
        self.assertEqual(re.findall(r"(?m)^  [a-z][a-z0-9-]*:$", gpu), ["  backend:"])
        self.assertIn("driver: nvidia", gpu)
        self.assertIn("capabilities: [gpu]", gpu)


if __name__ == "__main__":
    unittest.main()
