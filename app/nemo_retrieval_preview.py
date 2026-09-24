"""No-key preview of the regex rules configured for NeMo Retrieval Rails."""

from pathlib import Path
import re
from typing import Sequence

import yaml

from app.document_authorization import SecuredDocument


DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "guardrails" / "day14" / "config.yml"
)


def load_retrieval_patterns(config_path: Path = DEFAULT_CONFIG_PATH) -> tuple[re.Pattern[str], ...]:
    """Load the same patterns consumed by NeMo's `regex check retrieval` flow."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    retrieval = config["rails"]["config"]["regex_detection"]["retrieval"]
    flags = re.IGNORECASE if retrieval.get("case_insensitive", False) else 0
    return tuple(re.compile(pattern, flags) for pattern in retrieval["patterns"])


def apply_local_retrieval_rail_preview(
    documents: Sequence[SecuredDocument],
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> tuple[list[SecuredDocument], list[str]]:
    """Mirror the documented regex retrieval-rail filtering for the local demo."""
    patterns = load_retrieval_patterns(config_path)
    allowed: list[SecuredDocument] = []
    removed_ids: list[str] = []
    for document in documents:
        if any(pattern.search(document.content) for pattern in patterns):
            removed_ids.append(document.article_id)
        else:
            allowed.append(document)
    return allowed, removed_ids
