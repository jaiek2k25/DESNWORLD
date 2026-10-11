"""
DESNWORLD command-line interface.

Used by the GitHub Actions `generate-scenarios` workflow and for local runs:

    python -m desnworld.cli \
        --question "How might AI regulation affect semiconductor stocks over 12 months?" \
        --domain stock_market_education \
        --horizon 12 \
        --evidence-file evidence.json \
        --output report.json

Also:
    python -m desnworld.cli --validate-only report.json   # schema check only
    python -m desnworld.cli ... --mock                    # offline demo run
    python -m desnworld.cli --expand alt-1 --from-report report.json --output out.json

Exit codes:
    0  success
    2  input / configuration error
    3  AI provider error (rate limit, timeout, credentials, transport)
    4  schema validation error
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config
from .engine import ScenarioEngine
from .errors import (
    EngineError,
    InputValidationError,
    MissingCredentialsError,
    ProviderError,
    SchemaValidationError,
)
from .report import report_to_markdown, save_report
from .schema import DOMAINS, assert_valid_report, find_scenario


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="desnworld",
        description="DESNWORLD — AI scenario exploration engine (possibilities, not predictions).",
    )
    parser.add_argument("--question", help="The question to explore.")
    parser.add_argument(
        "--domain",
        choices=list(DOMAINS),
        help="Scenario domain.",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        dest="horizon_months",
        help="Time horizon in months (1-120).",
    )
    parser.add_argument(
        "--evidence-file",
        help="JSON file with a list of evidence items [{text, source_uri?, kind?, note?}].",
    )
    parser.add_argument("--output", default="report.json", help="Output report path (JSON).")
    parser.add_argument("--markdown", action="store_true", help="Also write a Markdown summary.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use the deterministic offline mock provider (no API key needed).",
    )
    parser.add_argument(
        "--validate-only",
        metavar="REPORT",
        help="Only validate an existing report JSON file, then exit.",
    )
    parser.add_argument(
        "--expand",
        metavar="SCENARIO_ID",
        help="Expand an existing report: generate 3 sub-branches under SCENARIO_ID.",
    )
    parser.add_argument(
        "--from-report",
        metavar="REPORT",
        help="Input report for --expand (default: the --output file).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging.")
    return parser


def _load_evidence(path: Optional[str]) -> List[Dict[str, Any]]:
    if not path:
        return []
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("evidence"), list):
        return raw["evidence"]
    if isinstance(raw, list):
        return raw
    raise InputValidationError(
        "The evidence file must contain a JSON list of evidence items, "
        "or an object with an 'evidence' list.",
        problems=["evidence-file: unexpected structure"],
    )


def _fail(exc: EngineError) -> int:
    print(json.dumps(exc.to_payload(), ensure_ascii=False, indent=2), file=sys.stderr)
    if isinstance(exc, (InputValidationError, MissingCredentialsError)):
        return 2
    if isinstance(exc, ProviderError):
        return 3
    if isinstance(exc, SchemaValidationError):
        return 4
    return 1


def _make_engine(mock: bool) -> ScenarioEngine:
    if mock:
        from .providers import MockScenarioProvider

        return ScenarioEngine(MockScenarioProvider())
    from .providers import OpenAIProvider

    problems = Config.validate(require_llm=True)
    if problems:
        raise MissingCredentialsError(
            "Cannot run generation without AI provider credentials.",
            hint=" ".join(problems),
        )
    return ScenarioEngine(OpenAIProvider())


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # --- validate-only mode -------------------------------------------
    if args.validate_only:
        try:
            raw = json.loads(Path(args.validate_only).read_text(encoding="utf-8"))
            assert_valid_report(raw, context="scenario report file")
        except (OSError, json.JSONDecodeError) as exc:
            return _fail(
                InputValidationError(
                    f"Could not read report file: {exc}",
                    problems=[f"validate-only: {exc}"],
                )
            )
        except SchemaValidationError as exc:
            return _fail(exc)
        print(f"OK: {args.validate_only} is a valid DESNWORLD scenario report.")
        return 0

    # --- expand mode ---------------------------------------------------
    if args.expand:
        if not args.question and not args.from_report and not args.output:
            pass
        input_path = args.from_report or args.output
        try:
            raw = json.loads(Path(input_path).read_text(encoding="utf-8"))
            assert_valid_report(raw, context="input scenario report")
        except (OSError, json.JSONDecodeError) as exc:
            return _fail(
                InputValidationError(
                    f"Could not read input report '{input_path}': {exc}",
                    problems=[f"from-report: {exc}"],
                    hint="Run a generation first, or pass --from-report explicitly.",
                )
            )
        except SchemaValidationError as exc:
            return _fail(exc)
        if find_scenario(raw, args.expand) is None:
            return _fail(
                SchemaValidationError(
                    f"Scenario '{args.expand}' does not exist in '{input_path}'.",
                    problems=[f"expand: unknown scenario id '{args.expand}'"],
                )
            )
        try:
            engine = _make_engine(args.mock)
            expanded = engine.expand_branch(raw, args.expand)
        except EngineError as exc:
            return _fail(exc)
        save_report(expanded, args.output)
        if args.markdown:
            Path(args.output).with_suffix(".md").write_text(
                report_to_markdown(expanded), encoding="utf-8"
            )
        print(f"Expanded '{args.expand}' -> {args.output}")
        return 0

    # --- generation mode ----------------------------------------------
    if not args.question or not args.domain or args.horizon_months is None:
        return _fail(
            InputValidationError(
                "Generation requires --question, --domain, and --horizon.",
                problems=[
                    p
                    for p, present in (
                        ("question: missing", bool(args.question)),
                        ("domain: missing", bool(args.domain)),
                        ("horizon_months: missing", args.horizon_months is not None),
                    )
                    if not present
                ],
                hint="Example: --question '...' --domain general --horizon 12",
            )
        )

    try:
        evidence = _load_evidence(args.evidence_file)
    except EngineError as exc:
        return _fail(exc)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(
            InputValidationError(
                f"Could not read evidence file: {exc}",
                problems=[f"evidence-file: {exc}"],
            )
        )

    request = {
        "question": args.question,
        "domain": args.domain,
        "horizon_months": args.horizon_months,
        "evidence": evidence,
    }

    try:
        engine = _make_engine(args.mock)
        report = engine.generate(request)
    except EngineError as exc:
        return _fail(exc)

    save_report(report, args.output)
    if args.markdown:
        Path(args.output).with_suffix(".md").write_text(
            report_to_markdown(report), encoding="utf-8"
        )
    print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
