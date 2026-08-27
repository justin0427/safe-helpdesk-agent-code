"""CLI entry point for the Day 2 demo."""

import os

from dotenv import load_dotenv

from app.agent import HelpdeskAgent


def main() -> None:
    load_dotenv()

    model_name = os.getenv("MODEL_NAME")
    if not model_name:
        raise RuntimeError("Set MODEL_NAME in .env before running the demo.")

    message = input("你遇到什麼 IT 問題？\n> ").strip()
    if not message:
        raise ValueError("Please describe an IT problem.")

    agent = HelpdeskAgent(
        model_name=model_name,
        requested_by="demo.user",
    )
    print("\nAgent：")
    print(agent.run(message))


if __name__ == "__main__":
    main()
