"""Load the Day 14 configuration with the optional NeMo Guardrails runtime."""

from pathlib import Path

from nemoguardrails import RailsConfig


CONFIG_DIR = Path(__file__).resolve().parents[1] / "guardrails" / "day14"


def main() -> None:
    config = RailsConfig.from_path(str(CONFIG_DIR))
    print(
        "NeMo config loaded:",
        ", ".join(config.rails.retrieval.flows),
    )


if __name__ == "__main__":
    main()
