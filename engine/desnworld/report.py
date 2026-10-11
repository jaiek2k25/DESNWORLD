"""
Report serialization helpers: JSON I/O and a human-readable Markdown summary.

The JSON document is the canonical artifact (uploaded by GitHub Actions,
imported by the web interface). The Markdown summary is a convenience for
humans reviewing workflow runs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union

from .schema import assert_valid_report

PathLike = Union[str, Path]


def report_to_json(report: Dict[str, Any], *, indent: int = 2) -> str:
    """Serialize a validated report to JSON text."""
    assert_valid_report(report)
    return json.dumps(report, ensure_ascii=False, indent=indent) + "\n"


def save_report(report: Dict[str, Any], path: PathLike) -> Path:
    """Validate and write a report to `path`."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report_to_json(report), encoding="utf-8")
    return out


def load_report(path: PathLike) -> Dict[str, Any]:
    """Load and validate a report from `path`."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return assert_valid_report(raw, context="scenario report file")


def report_to_markdown(report: Dict[str, Any]) -> str:
    """Render a concise Markdown summary of a report (does not re-validate)."""
    request = report.get("request", {})
    horizon = request.get("horizon", {})
    baseline = report.get("baseline", {})
    lines = [
        f"# DESNWORLD scenario report — {report.get('report_id', '')}",
        "",
        f"*Generated: {report.get('generated_at', '')} · "
        f"engine {report.get('generator', {}).get('engine_version', '?')} · "
        f"provider `{report.get('generator', {}).get('provider', '?')}` "
        f"model `{report.get('generator', {}).get('model', '?')}`*",
        "",
        f"**Question:** {request.get('question', '')}",
        f"**Domain:** {request.get('domain', '')} · **Horizon:** {horizon.get('label', '')}",
        "",
        "> " + report.get("disclaimer", ""),
        "",
        f"**Data status:** {report.get('data_status', {}).get('message', '')}",
        "",
        "## Baseline",
        f"**{baseline.get('title', '')}** ({baseline.get('stance', {}).get('qualitative', '')})",
        "",
        baseline.get("narrative", ""),
        "",
        "## Alternatives",
    ]
    for alt in report.get("alternatives", []):
        lines += [
            f"### {alt.get('label', '')}: {alt.get('title', '')} "
            f"({alt.get('stance', {}).get('qualitative', '')})",
            "",
            alt.get("narrative", ""),
            "",
            "**Triggers:**",
        ]
        for trig in alt.get("triggers", []):
            lines.append(f"- *{trig.get('event', '')}* — {trig.get('description', '')}")
        lines.append("")

    comparison = report.get("comparison", {})
    lines += ["## Comparison", "", comparison.get("summary", ""), "", "**Key differences:**"]
    lines += [f"- {item}" for item in comparison.get("key_differences", [])]
    lines += ["", "**What would change the outlook:**"]
    lines += [f"- {item}" for item in comparison.get("what_would_change_the_outlook", [])]

    lines += ["", "## Uncertainties"]
    for u in report.get("uncertainties", []):
        lines.append(
            f"- ({u.get('impact', '')}) {u.get('statement', '')} "
            f"— missing evidence: {u.get('missing_evidence', '')}"
        )

    lines += ["", "## Missing information"]
    lines += [f"- {item}" for item in report.get("missing_information", [])]

    lines += ["", "## Limitations"]
    lines += [f"- {item}" for item in report.get("limitations", [])]

    lines += ["", "## Evidence ledger"]
    for item in report.get("evidence_ledger", []):
        uri = f" — {item.get('source_uri')}" if item.get("source_uri") else ""
        lines.append(f"- `[{item.get('kind', '')}]` {item.get('text', '')}{uri}")

    lines.append("")
    return "\n".join(lines)
