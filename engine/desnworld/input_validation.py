"""
Input validation for DESNWORLD scenario requests.

A scenario request is the user-facing input:

    {
      "question": "How might AI regulation affect semiconductor stocks ...?",
      "domain": "stock_market_education",
      "horizon_months": 12,
      "evidence": [
        {"text": "...", "source_uri": "https://...", "kind": "user_supplied_fact"}
      ]
    }

Validation is pure (no I/O) so it can run in the CLI, the pipeline, the local
dev server and tests alike.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from .config import Config
from .errors import InputValidationError
from .schema import DOMAINS, PROVENANCE_KINDS, make_evidence_item

MIN_QUESTION_LENGTH = 10
MIN_HORIZON_MONTHS = 1
MAX_HORIZON_MONTHS = 120
MAX_EVIDENCE_TEXT_LENGTH = 4000

_DOMAIN_ALIASES = {
    "general": "general",
    "stock_market_education": "stock_market_education",
    "stock market education": "stock_market_education",
    "stock-market-education": "stock_market_education",
    "stockmarket": "stock_market_education",
    "stock_market": "stock_market_education",
    "business": "business",
    "technology": "technology",
    "tech": "technology",
}


def normalize_domain(raw: Any) -> str:
    """Map user input to a canonical domain slug (raises on unknown values)."""
    if not isinstance(raw, str):
        raise InputValidationError("Domain must be a string.", problems=["domain: not a string"])
    key = raw.strip().lower()
    slug = _DOMAIN_ALIASES.get(key) or _DOMAIN_ALIASES.get(key.replace(" ", "_"))
    if slug is None:
        raise InputValidationError(
            f"Unknown domain '{raw}'.",
            problems=[f"domain: must be one of {list(DOMAINS)}"],
            hint="Choose General, Stock Market Education, Business, or Technology.",
        )
    return slug


def horizon_label(months: int) -> str:
    """Human-readable label for a horizon in months."""
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''}"
    years = months // 12
    remainder = months % 12
    parts = [f"{years} year{'s' if years != 1 else ''}"]
    if remainder:
        parts.append(f"{remainder} month{'s' if remainder != 1 else ''}")
    return " ".join(parts)


def _validate_http_url(value: Any, path: str, problems: List[str]) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        problems.append(f"{path}: must be a string URL")
        return None
    parsed = urlparse(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        problems.append(f"{path}: must be a valid http(s) URL")
        return None
    return value.strip()


def _normalize_evidence(
    raw_evidence: Any, problems: List[str], *, max_items: int
) -> List[Dict[str, Any]]:
    if raw_evidence is None:
        return []
    if not isinstance(raw_evidence, list):
        problems.append("evidence: must be a list of evidence items")
        return []
    if len(raw_evidence) > max_items:
        problems.append(
            f"evidence: at most {max_items} items are allowed (found {len(raw_evidence)})"
        )
        return []

    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_evidence):
        path = f"evidence[{index}]"
        if isinstance(item, str):
            item = {"text": item}
        if not isinstance(item, dict):
            problems.append(f"{path}: must be an object with a 'text' field")
            continue

        text = item.get("text")
        if not isinstance(text, str) or len(text.strip()) < 3:
            problems.append(f"{path}.text: must be at least 3 characters")
            continue
        if len(text) > MAX_EVIDENCE_TEXT_LENGTH:
            problems.append(
                f"{path}.text: must be at most {MAX_EVIDENCE_TEXT_LENGTH} characters"
            )
            continue

        kind = item.get("kind") or "user_supplied_fact"
        if kind not in PROVENANCE_KINDS:
            problems.append(f"{path}.kind: must be one of {list(PROVENANCE_KINDS)}")
            continue

        source_uri = _validate_http_url(item.get("source_uri"), f"{path}.source_uri", problems)
        if kind == "sourced_fact" and source_uri is None:
            problems.append(
                f"{path}: kind 'sourced_fact' requires a source_uri "
                "(claims must not carry fabricated provenance)"
            )
            continue

        note = item.get("note")
        if note is not None and not isinstance(note, str):
            problems.append(f"{path}.note: must be a string")
            continue

        normalized.append(
            make_evidence_item(
                f"e{index + 1}",
                text,
                kind=kind,
                source_uri=source_uri,
                note=note.strip() if isinstance(note, str) else None,
            )
        )
    return normalized


def validate_request(
    question: Any,
    domain: Any,
    horizon_months: Any,
    evidence: Any = None,
    *,
    max_question_length: Optional[int] = None,
    max_evidence_items: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Validate and normalize a scenario request.

    Returns the normalized request dict. Raises InputValidationError listing
    every problem found when the request is not usable.
    """
    problems: List[str] = []
    max_q = max_question_length or Config.MAX_QUESTION_LENGTH
    max_e = max_evidence_items or Config.MAX_EVIDENCE_ITEMS

    # --- question ---
    cleaned_question = ""
    if not isinstance(question, str):
        problems.append("question: must be a string")
    else:
        cleaned_question = re.sub(r"\s+", " ", question).strip()
        if len(cleaned_question) < MIN_QUESTION_LENGTH:
            problems.append(
                f"question: must be at least {MIN_QUESTION_LENGTH} characters "
                "(describe what you want to explore)"
            )
        elif len(cleaned_question) > max_q:
            problems.append(f"question: must be at most {max_q} characters")

    # --- domain ---
    cleaned_domain = None
    try:
        cleaned_domain = normalize_domain(domain)
    except InputValidationError as exc:
        problems.extend(exc.problems or [exc.message])

    # --- horizon ---
    months: Optional[int] = None
    if isinstance(horizon_months, bool):
        problems.append("horizon_months: must be an integer number of months")
    elif isinstance(horizon_months, str) and horizon_months.strip().isdigit():
        horizon_months = int(horizon_months.strip())
    if isinstance(horizon_months, int) and not isinstance(horizon_months, bool):
        if not (MIN_HORIZON_MONTHS <= horizon_months <= MAX_HORIZON_MONTHS):
            problems.append(
                f"horizon_months: must be between {MIN_HORIZON_MONTHS} and "
                f"{MAX_HORIZON_MONTHS} (found {horizon_months})"
            )
        else:
            months = horizon_months
    elif horizon_months is not None and months is None and not any(
        p.startswith("horizon_months") for p in problems
    ):
        problems.append("horizon_months: must be an integer number of months")

    # --- evidence ---
    normalized_evidence = _normalize_evidence(evidence, problems, max_items=max_e)

    if problems:
        raise InputValidationError(
            f"The scenario request is invalid: {len(problems)} problem(s) found.",
            problems=problems,
            hint="Fix the highlighted fields and try again.",
        )

    assert cleaned_domain is not None and months is not None
    return {
        "question": cleaned_question,
        "domain": cleaned_domain,
        "horizon": {"months": months, "label": horizon_label(months)},
        "evidence": normalized_evidence,
    }


def request_from_mapping(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a request supplied as a JSON mapping (CLI/server/Actions)."""
    if not isinstance(payload, dict):
        raise InputValidationError(
            "The request payload must be a JSON object.",
            problems=["payload: not an object"],
        )
    return validate_request(
        payload.get("question"),
        payload.get("domain"),
        payload.get("horizon_months", payload.get("horizon")),
        payload.get("evidence"),
    )
