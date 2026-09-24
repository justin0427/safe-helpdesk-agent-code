import unittest
from unittest.mock import patch

from app.model_settings import ModelSettings


class ModelSettingsTests(unittest.TestCase):
    def test_reads_generic_openai_compatible_settings(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "MODEL_NAME": "local-model",
                "MODEL_API_KEY": "local-key",
                "MODEL_BASE_URL": "http://model-host/v1",
            },
            clear=True,
        ):
            settings = ModelSettings.from_env()

        self.assertTrue(settings.is_ready)
        self.assertEqual(settings.model_name, "local-model")
        self.assertEqual(settings.api_key, "local-key")
        self.assertEqual(settings.base_url, "http://model-host/v1")
        self.assertEqual(settings.provider_label, "OpenAI-compatible")

    def test_keeps_openai_environment_compatibility(self) -> None:
        with patch.dict(
            "os.environ",
            {"MODEL_NAME": "openai-model", "OPENAI_API_KEY": "openai-key"},
            clear=True,
        ):
            settings = ModelSettings.from_env()

        self.assertTrue(settings.is_ready)
        self.assertEqual(settings.api_key, "openai-key")
        self.assertIsNone(settings.base_url)
        self.assertEqual(settings.provider_label, "OpenAI")

    def test_requires_both_model_and_credentials(self) -> None:
        with patch.dict("os.environ", {"MODEL_NAME": "local-model"}, clear=True):
            settings = ModelSettings.from_env()

        self.assertFalse(settings.is_ready)


if __name__ == "__main__":
    unittest.main()
