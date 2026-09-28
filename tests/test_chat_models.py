import unittest
from unittest.mock import patch

from app.chat_models import build_chat_model, message_text


class ChatModelTests(unittest.TestCase):
    def test_reads_text_from_native_content_blocks(self) -> None:
        content = [{"type": "text", "text": "Gemini response", "extras": {}}]

        self.assertEqual(message_text(content), "Gemini response")

    @patch("app.chat_models.ChatGoogleGenerativeAI")
    def test_uses_native_google_client_for_gemini(self, google_model) -> None:
        build_chat_model(
            model_name="gemini-3.5-flash-lite",
            api_key="gemini-key",
            base_url=None,
            timeout_seconds=60,
            max_tokens=800,
        )

        google_model.assert_called_once_with(
            model="gemini-3.5-flash-lite",
            api_key="gemini-key",
            request_timeout=60,
            max_tokens=800,
            retries=0,
        )

    @patch("app.chat_models.ChatOpenAI")
    def test_keeps_openai_compatible_models(self, openai_model) -> None:
        build_chat_model(
            model_name="local-model",
            api_key="local-key",
            base_url="http://model-host/v1",
            timeout_seconds=20,
            max_tokens=600,
        )

        openai_model.assert_called_once_with(
            model="local-model",
            api_key="local-key",
            base_url="http://model-host/v1",
            temperature=0,
            timeout=20,
            max_tokens=600,
        )


if __name__ == "__main__":
    unittest.main()
