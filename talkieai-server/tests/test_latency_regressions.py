import unittest
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]


class LatencyRegressionTest(unittest.TestCase):
    def test_whisper_inference_does_not_move_model_to_cpu_per_request(self):
        source = (SERVER_ROOT / "app" / "core" / "whisper_voice.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn('self.model = self.model.to("cpu", torch.float32)', source)

    def test_mas_message_flow_has_no_fixed_processing_sleep(self):
        source = (SERVER_ROOT / "app" / "services" / "chat_service.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("time.sleep(0.5)", source)
        self.assertNotIn("time.sleep(1)", source)

    def test_mas_agents_return_the_generated_reply_directly(self):
        for agent in ("SOA", "GRA", "SCA"):
            source = (SERVER_ROOT / "mas" / agent / "app.py").read_text(
                encoding="utf-8"
            )
            self.assertIn('"assistant_message": assistant_reply', source)

        soa_source = (SERVER_ROOT / "mas" / "SOA" / "app.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '"status": "SOA triggered", "patient_id": patient_id, "assistant_message": assistant_reply',
            soa_source,
        )

    def test_chat_service_uses_direct_agent_reply_fast_path(self):
        source = (SERVER_ROOT / "app" / "services" / "chat_service.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('result_data.get("assistant_message")', source)

    def test_main_service_does_not_duplicate_normal_oa_user_write(self):
        source = (SERVER_ROOT / "app" / "services" / "chat_service.py").read_text(
            encoding="utf-8"
        )

        # Two writes remain only in the already-completed compatibility branches.
        self.assertEqual(source.count('"/receive_user_message"'), 2)

    def test_mas_ai_clients_are_reused_and_calls_do_not_block_event_loop(self):
        for agent in ("SOA", "GRA", "SCA"):
            helper_source = (SERVER_ROOT / "mas" / agent / "ai_helper.py").read_text(
                encoding="utf-8"
            )
            app_source = (SERVER_ROOT / "mas" / agent / "app.py").read_text(
                encoding="utf-8"
            )

            self.assertIn("_get_openai_client", helper_source)
            self.assertIn("_get_zhipu_client", helper_source)
            self.assertIn("await run_blocking(ask_gpt", app_source)


if __name__ == "__main__":
    unittest.main()
