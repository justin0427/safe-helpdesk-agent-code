"""CLI entry point kept as a small alternative to the local web console."""

from dotenv import load_dotenv

from app.agent import HelpdeskAgent
from app.model_settings import ModelSettings


def main() -> None:
    load_dotenv()

    settings = ModelSettings.from_env()
    if not settings.is_ready:
        raise RuntimeError("Set MODEL_NAME and model credentials in .env before running the demo.")

    message = input("你遇到什麼 IT 問題？\n> ").strip()
    if not message:
        raise ValueError("Please describe an IT problem.")

    agent = HelpdeskAgent(
        model_name=settings.model_name,
        model_api_key=settings.api_key,
        model_base_url=settings.base_url,
        requested_by="demo.user",
    )
    print("\nAgent：")
    print(agent.run(message))


if __name__ == "__main__":
    main()
