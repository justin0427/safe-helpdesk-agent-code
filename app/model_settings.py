"""Environment-backed configuration for OpenAI-compatible chat models."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ModelSettings:
    model_name: str | None
    api_key: str | None
    base_url: str | None

    @classmethod
    def from_env(cls) -> "ModelSettings":
        return cls(
            model_name=_optional_env("MODEL_NAME"),
            api_key=_optional_env("MODEL_API_KEY") or _optional_env("OPENAI_API_KEY"),
            base_url=_optional_env("MODEL_BASE_URL") or _optional_env("OPENAI_BASE_URL"),
        )

    @property
    def is_ready(self) -> bool:
        return bool(self.model_name and self.api_key)

    @property
    def provider_label(self) -> str:
        return "OpenAI-compatible" if self.base_url else "OpenAI"


def _optional_env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None
