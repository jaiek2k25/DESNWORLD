"""Schema validation tests: versioning, structure, provenance, tree shape."""

from __future__ import annotations

import copy

import pytest

from desnworld.errors import SchemaValidationError
from desnworld.schema import (
    SCHEMA_VERSION,
    assert_valid_report,
    find_scenario,
    is_compatible_version,
    make_assumption,
    make_comparison,
    make_scenario,
    make_trigger,
    make_uncertainty,
    validate_report,
)


def _minimal_valid_report() -> dict:
    scenario_kwargs = dict(
        stance="plausible",
        stance_note="Qualitative only; not a probability estimate.",
        assumptions=[
            make_assumption("a1", "A reasonable baseline assumption.", kind="ai_assumption")
        ],
        triggers=[make_trigger("t1", "A trigger event happens", "It moves the path.")],
        possible_consequences=["Something happens."],
        indicators_to_watch=["An indicator."],
    )
    baseline = make_scenario("baseline", "Baseline", "Baseline path", "Baseline narrative text.", **scenario_kwargs)
    alts = []
    for i, title in enumerate(["Upside drift", "Downside stress", "Regime shift"], start=1):
        alt_kwargs = copy.deepcopy(scenario_kwargs)
        alt_kwargs["triggers"] = [make_trigger(f"t{i}", f"Distinct trigger event {i}", "It moves the path.")]
        alts.append(
            make_scenario(f"alt-{i}", f"Alt {i}", title, f"Narrative for {title}.", **alt_kwargs)
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": "rpt-test",
        "generated_at": "2026-10-11T00:00:00+00:00",
        "generator": {"name": "DESNWORLD", "engine_version": "0.1.0"},
        "request": {
            "question": "A perfectly reasonable question here?",
            "domain": "general",
            "horizon": {"months": 12, "label": "1 year"},
            "evidence": [],
        },
        "disclaimer": "Possibilities, not predictions.",
        "data_status": {
            "live_market_data_checked": False,
            "sources": [],
            "message": "No live sources were queried in this run.",
        },
        "baseline": baseline,
        "alternatives": alts,
        "comparison": make_comparison(
            "A summary comparing the baseline and three alternatives in detail.",
            [
                {
                    "dimension": "Direction",
                    "baseline": "Flat",
                    "alternatives": {"alt-1": "Up", "alt-2": "Down", "alt-3": "Sideways-new"},
                }
            ],
            ["They differ in direction."],
            ["A trigger event would change the outlook."],
        ),
        "uncertainties": [
            make_uncertainty("u1", "Something is uncertain.", impact="high", missing_evidence="More data.")
        ],
        "missing_information": ["Something is missing."],
        "limitations": ["A limitation."],
        "evidence_ledger": [],
    }


class TestSchemaVersioning:
    def test_current_version_is_compatible(self):
        assert is_compatible_version(SCHEMA_VERSION)

    def test_same_major_older_minor(self):
        assert is_compatible_version("1.0.0")

    def test_newer_minor_is_rejected(self):
        assert not is_compatible_version("1.99.0")

    def test_other_major_is_rejected(self):
        assert not is_compatible_version("2.0.0")

    def test_garbage_is_rejected(self):
        assert not is_compatible_version("banana")

    def test_incompatible_version_is_reported(self):
        doc = _minimal_valid_report()
        doc["schema_version"] = "2.0.0"
        problems = validate_report(doc)
        assert any("schema_version" in p for p in problems)


class TestValidDocument:
    def test_minimal_report_passes(self):
        assert validate_report(_minimal_valid_report()) == []

    def test_assert_valid_report_returns_doc(self):
        doc = _minimal_valid_report()
        assert assert_valid_report(doc) is doc

    def test_engine_generated_report_passes(self, generated_report):
        assert validate_report(generated_report) == []

    def test_find_scenario(self, generated_report):
        assert find_scenario(generated_report, "baseline") is not None
        assert find_scenario(generated_report, "alt-2") is not None
        assert find_scenario(generated_report, "nope") is None


class TestStructuralFailures:
    def test_not_an_object(self):
        assert validate_report(["nope"]) == ["report: must be a JSON object"]

    def test_missing_baseline(self):
        doc = _minimal_valid_report()
        del doc["baseline"]
        assert any("baseline" in p for p in validate_report(doc))

    @pytest.mark.parametrize("count", [0, 1, 2, 4])
    def test_alternatives_count(self, count):
        doc = _minimal_valid_report()
        alts = doc["alternatives"][:count]
        if count == 4:
            alts = alts + [copy.deepcopy(alts[-1])]
        doc["alternatives"] = alts
        problems = validate_report(doc)
        assert any("exactly 3 alternative" in p for p in problems)

    def test_duplicate_alternative_titles(self):
        doc = _minimal_valid_report()
        doc["alternatives"][1]["title"] = doc["alternatives"][0]["title"]
        assert any("meaningfully different" in p for p in validate_report(doc))

    def test_identical_trigger_sets(self):
        doc = _minimal_valid_report()
        doc["alternatives"][1]["triggers"] = copy.deepcopy(doc["alternatives"][0]["triggers"])
        doc["alternatives"][1]["triggers"][0]["id"] = "tX"
        assert any("identical trigger set" in p for p in validate_report(doc))

    def test_missing_comparison(self):
        doc = _minimal_valid_report()
        doc["comparison"] = {}
        problems = validate_report(doc)
        assert any("comparison.summary" in p for p in problems)

    def test_comparison_dimension_needs_three_alternatives(self):
        doc = _minimal_valid_report()
        doc["comparison"]["dimensions"][0]["alternatives"] = {"alt-1": "Up"}
        assert any("exactly 3 scenario ids" in p for p in validate_report(doc))

    def test_missing_uncertainties(self):
        doc = _minimal_valid_report()
        doc["uncertainties"] = []
        assert any("uncertainties" in p for p in validate_report(doc))

    def test_horizon_bounds(self):
        doc = _minimal_valid_report()
        doc["request"]["horizon"]["months"] = 500
        assert any("horizon" in p for p in validate_report(doc))


class TestProvenanceRules:
    def test_assumption_sourced_fact_requires_backing(self):
        doc = _minimal_valid_report()
        doc["baseline"]["assumptions"][0] = make_assumption(
            "a1", "An unbacked source claim.", kind="sourced_fact"
        )
        problems = validate_report(doc)
        assert any("fabricated provenance" in p for p in problems)

    def test_assumption_sourced_fact_with_evidence_ref_is_fine(self):
        doc = _minimal_valid_report()
        doc["request"]["evidence"] = [
            {"id": "e1", "text": "User supplied evidence text.", "kind": "user_supplied_fact", "source_uri": None, "note": None}
        ]
        doc["evidence_ledger"] = [
            {"id": "e1", "kind": "user_supplied_fact", "text": "User supplied evidence text.", "source_uri": None, "evidence_ref": None, "note": None}
        ]
        doc["baseline"]["assumptions"][0] = make_assumption(
            "a1", "Backed by user evidence.", kind="sourced_fact", evidence_ref="e1"
        )
        assert validate_report(doc) == []

    def test_dangling_evidence_ref(self):
        doc = _minimal_valid_report()
        doc["baseline"]["assumptions"][0] = make_assumption(
            "a1", "Points at nothing.", kind="user_supplied_fact", evidence_ref="e999"
        )
        assert any("does not match any request evidence id" in p for p in validate_report(doc))

    def test_ledger_sourced_fact_requires_backing(self):
        doc = _minimal_valid_report()
        doc["evidence_ledger"] = [
            {"id": "e1", "kind": "sourced_fact", "text": "Invented source claim.", "source_uri": None, "evidence_ref": None}
        ]
        assert any("fabricated provenance" in p for p in validate_report(doc))

    def test_request_evidence_sourced_fact_requires_uri(self):
        doc = _minimal_valid_report()
        doc["request"]["evidence"] = [
            {"id": "e1", "text": "Invented source claim here.", "kind": "sourced_fact", "source_uri": None}
        ]
        assert any("source_uri is missing" in p for p in validate_report(doc))


class TestTreeRules:
    def test_children_must_be_three(self):
        doc = _minimal_valid_report()
        parent = doc["alternatives"][0]
        child = make_scenario(
            "alt-1.c1", "C1", "Only child", "Narrative of the only child.",
            stance="plausible",
            stance_note="Qualitative only; not a probability estimate.",
            assumptions=[make_assumption("x", "An assumption here.", kind="ai_assumption")],
            triggers=[make_trigger("y", "A trigger event", "A description here.")],
            possible_consequences=["Something."],
            indicators_to_watch=["Indicator."],
            parent_id="alt-1",
        )
        parent["children"] = [child]
        assert any("exactly 3 sub-branches" in p for p in validate_report(doc))

    def test_parent_id_must_match(self):
        doc = _minimal_valid_report()
        children = []
        for i in range(3):
            children.append(
                make_scenario(
                    f"alt-1.c{i+1}", f"C{i+1}", f"Child {i+1} title", "Child narrative here.",
                    stance="plausible",
                    stance_note="Qualitative only; not a probability estimate.",
                    assumptions=[make_assumption("x", "An assumption here.", kind="ai_assumption")],
                    triggers=[make_trigger("y", "A trigger event", "A description here.")],
                    possible_consequences=["Something."],
                    indicators_to_watch=["Indicator."],
                    parent_id="wrong-parent",
                )
            )
        doc["alternatives"][0]["children"] = children
        assert any("must equal the parent node id" in p for p in validate_report(doc))

    def test_depth_limit(self):
        doc = _minimal_valid_report()

        def build_children(parent_id: str, depth: int):
            node = make_scenario(
                f"{parent_id}.c1", "C1", f"Title at {parent_id}", "A child narrative here.",
                stance="plausible",
                stance_note="Qualitative only; not a probability estimate.",
                assumptions=[make_assumption("x", "An assumption here.", kind="ai_assumption")],
                triggers=[make_trigger("y", "A trigger event", "A description here.")],
                possible_consequences=["Something."],
                indicators_to_watch=["Indicator."],
                parent_id=parent_id,
            )
            # Build a legal sibling set for the parent first
            siblings = [node]
            for i in (2, 3):
                siblings.append(
                    make_scenario(
                        f"{parent_id}.c{i}", f"C{i}", f"Title at {parent_id} {i}", "A child narrative here.",
                        stance="plausible",
                        stance_note="Qualitative only; not a probability estimate.",
                        assumptions=[make_assumption("x", "An assumption here.", kind="ai_assumption")],
                        triggers=[make_trigger("y", "A trigger event", "A description here.")],
                        possible_consequences=["Something."],
                        indicators_to_watch=["Indicator."],
                        parent_id=parent_id,
                    )
                )
            if depth > 0:
                for child in siblings:
                    child["children"] = build_children(child["id"], depth - 1)
            return siblings

        # root -> children -> grandchildren -> great-grandchildren (too deep)
        doc["alternatives"][0]["children"] = build_children("alt-1", depth=2)
        problems = validate_report(doc)
        assert any("tree depth exceeds" in p for p in problems)

    def test_assert_valid_report_raises_with_problems(self):
        doc = _minimal_valid_report()
        doc["alternatives"] = []
        with pytest.raises(SchemaValidationError) as exc:
            assert_valid_report(doc)
        assert exc.value.problems
        assert exc.value.to_payload()["error"] == "schema_validation_error"
