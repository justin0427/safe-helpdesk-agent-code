"""Environment-backed configuration for chat models."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ModelSettings:
    model_name: str | None
    api_key: str | None
    base_url: str | None

    @classmethod
    def from_env(cls) -> "ModelSettings":
        model_name = _optional_env("MODEL_NAME")
        base_url = _optional_env("MODEL_BASE_URL") or _optional_env("OPENAI_BASE_URL")
        if is_gemini_model(model_name, base_url):
            api_key = _optional_env("GEMINI_API_KEY") or _optional_env("GOOGLE_API_KEY")
        else:
            api_key = _optional_env("MODEL_API_KEY") or _optional_env("OPENAI_API_KEY")
        return cls(
            model_name=model_name,
            api_key=api_key,
            base_url=base_url,
        )

    @property
    def is_ready(self) -> bool:
        return bool(self.model_name and self.api_key)

    @property
    def provider_label(self) -> str:
        if is_gemini_model(self.model_name, self.base_url):
            return "Google Gemini"
        return "OpenAI-compatible" if self.base_url else "OpenAI"


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def is_gemini_model(model_name: str | None, base_url: str | None) -> bool:
    return bool(
        (model_name and model_name.startswith("gemini-"))
        or (base_url and "generativelanguage.googleapis.com" in base_url)
    )
