"""Build the configured LangChain chat model."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.model_settings import is_gemini_model


def build_chat_model(
    *,
    model_name: str,
    api_key: str,
    base_url: str | None,
    timeout_seconds: float,
    max_tokens: int,
) -> BaseChatModel:
    if is_gemini_model(model_name, base_url):
        return ChatGoogleGenerativeAI(
            model=model_name,
            api_key=api_key,
            request_timeout=timeout_seconds,
            max_tokens=max_tokens,
            retries=0,
        )
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
        timeout=timeout_seconds,
        max_tokens=max_tokens,
    )


def message_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part["text"]
            for part in content
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    return str(content)
