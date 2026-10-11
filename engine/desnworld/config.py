"""
DESNWORLD configuration.

Pattern adapted from MiroFish (https://github.com/666ghj/MiroFish),
backend/app/config.py — Copyright (c) MiroFish authors and contributors,
AGPL-3.0. Rewritten for DESNWORLD configuration keys.

Configuration is loaded from environment variables, optionally populated from a
project-root `.env` file for local development. GitHub Actions supplies the
same variables from repository secrets.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is a declared dependency
    load_dotenv = None  # type: ignore[assignment]


def _load_env() -> None:
    if load_dotenv is None:
        return
    project_root = Path(__file__).resolve().parents[2]
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=True)


_load_env()


class Config:
    """Runtime configuration for the DESNWORLD engine."""

    # LLM provider (any OpenAI-compatible Chat Completions endpoint).
    LLM_API_KEY: Optional[str] = os.environ.get("LLM_API_KEY")
    LLM_BASE_URL: str = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL_NAME: str = os.environ.get("LLM_MODEL_NAME", "gpt-4o-mini")
    LLM_TIMEOUT_SECONDS: float = float(os.environ.get("LLM_TIMEOUT_SECONDS", "90"))

    # Engine behaviour.
    MAX_QUESTION_LENGTH: int = int(os.environ.get("MAX_QUESTION_LENGTH", "2000"))
    MAX_EVIDENCE_ITEMS: int = int(os.environ.get("MAX_EVIDENCE_ITEMS", "20"))

    # Local dev API server (engine/desnworld/server.py).
    DESNWORLD_HOST: str = os.environ.get("DESNWORLD_HOST", "127.0.0.1")
    DESNWORLD_PORT: int = int(os.environ.get("DESNWORLD_PORT", "8787"))

    # Honesty flag for the stock-market education module. The prototype ships
    # with NO live market-data adapter. Only set MARKET_DATA_CHECKED=true when a
    # real adapter queried live sources during the current run.
    MARKET_DATA_CHECKED: bool = (
        os.environ.get("MARKET_DATA_CHECKED", "false").strip().lower() == "true"
    )

    @classmethod
    def validate(cls, *, require_llm: bool = True) -> List[str]:
        """Return a list of configuration problems (empty when usable)."""
        errors: List[str] = []
        if require_llm and not cls.LLM_API_KEY:
            errors.append(
                "LLM_API_KEY is not configured. Set it in .env (local runs) or "
                "as a GitHub Actions secret (workflow runs)."
            )
        if require_llm and not cls.LLM_BASE_URL:
            errors.append("LLM_BASE_URL is not configured.")
        if require_llm and not cls.LLM_MODEL_NAME:
            errors.append("LLM_MODEL_NAME is not configured.")
        return errors
