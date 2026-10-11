"""Scenario branching tests: baseline + 3 alternatives, repair, sub-branches."""

from __future__ import annotations

import copy

import pytest

from desnworld.engine import ScenarioEngine
from desnworld.errors import SchemaValidationError
from desnworld.providers import MockScenarioProvider, ScriptedProvider
from desnworld.schema import validate_report


class TestBaselineAndAlternatives:
    def test_baseline_exists_and_is_not_null(self, generated_report):
        baseline = generated_report["baseline"]
        assert baseline["id"] == "baseline"
        assert baseline["title"]
        assert baseline["assumptions"]
        assert baseline["parent_id"] is None

    def test_exactly_three_alternatives(self, generated_report):
        assert len(generated_report["alternatives"]) == 3
        assert [a["id"] for a in generated_report["alternatives"]] == ["alt-1", "alt-2", "alt-3"]

    def test_alternatives_are_meaningfully_different(self, generated_report):
        titles = [a["title"].strip().lower() for a in generated_report["alternatives"]]
        assert len(set(titles)) == 3
        trigger_sets = [
            tuple(sorted(t["event"].strip().lower() for t in a["triggers"]))
            for a in generated_report["alternatives"]
        ]
        assert len(set(trigger_sets)) == 3

    def test_each_alternative_has_triggers_and_consequences(self, generated_report):
        for alt in generated_report["alternatives"]:
            assert alt["triggers"], alt["id"]
            assert alt["possible_consequences"], alt["id"]
            assert alt["indicators_to_watch"], alt["id"]
            assert alt["stance"]["qualitative"] in (
                "more_likely",
                "plausible",
                "less_likely",
                "unlikely",
            )

    def test_comparison_covers_all_scenarios(self, generated_report):
        comparison = generated_report["comparison"]
        assert comparison["summary"]
        for dim in comparison["dimensions"]:
            assert set(dim["alternatives"].keys()) == {"alt-1", "alt-2", "alt-3"}

    def test_uncertainties_and_missing_information(self, generated_report):
        assert generated_report["uncertainties"]
        assert generated_report["missing_information"]
        assert generated_report["limitations"]
        for u in generated_report["uncertainties"]:
            assert u["missing_evidence"]


class TestProvenanceTagging:
    def test_every_assumption_has_a_kind(self, generated_report):
        nodes = [generated_report["baseline"], *generated_report["alternatives"]]
        for node in nodes:
            for assumption in node["assumptions"]:
                assert assumption["kind"] in (
                    "sourced_fact",
                    "user_supplied_fact",
                    "ai_assumption",
                )

    def test_sourced_facts_are_backed(self, generated_report):
        nodes = [generated_report["baseline"], *generated_report["alternatives"]]
        for node in nodes:
            for assumption in node["assumptions"]:
                if assumption["kind"] == "sourced_fact":
                    assert assumption.get("source_uri") or assumption.get("evidence_ref")

    def test_data_status_is_honest_by_default(self, generated_report):
        status = generated_report["data_status"]
        assert status["live_market_data_checked"] is False
        assert "No live market data" in status["message"]

    def test_mock_reports_are_labelled_as_mock(self, generated_report):
        assert generated_report["generator"]["mock"] is True
        assert any("mock provider" in lim for lim in generated_report["limitations"])

    def test_unbacked_sourced_fact_is_downgraded(self, valid_request):
        provider = ScriptedProvider(
            [
                {
                    "scenario": {
                        "id": "baseline",
                        "label": "Baseline",
                        "title": "Continuation of visible conditions",
                        "narrative": "A baseline narrative of sufficient length.",
                        "stance": {"qualitative": "more_likely", "note": "Qualitative only."},
                        "assumptions": [
                            {
                                "id": "a1",
                                "text": "A claim with fake sourcing.",
                                "kind": "sourced_fact",
                                "confidence": "medium",
                                "evidence_ref": None,
                                "source_uri": None,
                            }
                        ],
                        "triggers": [
                            {"id": "t1", "event": "A trigger event here", "description": "A description."}
                        ],
                        "possible_consequences": ["A consequence."],
                        "indicators_to_watch": ["An indicator."],
                    }
                },
                {"alternatives": MockScenarioProvider()._alternatives("q")["alternatives"]},
                MockScenarioProvider()._uncertainties(),
                {"comparison": MockScenarioProvider()._comparison()["comparison"]},
            ]
        )
        report = ScenarioEngine(provider).generate(valid_request)
        kinds = [a["kind"] for a in report["baseline"]["assumptions"]]
        assert kinds == ["ai_assumption"]


class TestRepairLoop:
    def test_duplicate_alternative_titles_trigger_repair(self, valid_request):
        broken = MockScenarioProvider()._alternatives("q")["alternatives"]
        broken[1]["title"] = broken[0]["title"]
        fixed = MockScenarioProvider()._alternatives("q")["alternatives"]
        provider = ScriptedProvider(
            [
                {"scenario": MockScenarioProvider()._baseline("q")["scenario"]},
                {"alternatives": broken},
                {"alternatives": fixed},  # repair response
                MockScenarioProvider()._uncertainties(),
                {"comparison": MockScenarioProvider()._comparison()["comparison"]},
            ]
        )
        report = ScenarioEngine(provider).generate(valid_request)
        assert validate_report(report) == []
        assert len(provider.calls) == 5  # initial + repair

    def test_repair_failure_raises_schema_error(self, valid_request):
        broken = MockScenarioProvider()._alternatives("q")["alternatives"]
        broken[1]["title"] = broken[0]["title"]
        provider = ScriptedProvider(
            [
                {"scenario": MockScenarioProvider()._baseline("q")["scenario"]},
                {"alternatives": broken},
                {"alternatives": broken},  # repair also broken
            ]
        )
        with pytest.raises(SchemaValidationError) as exc:
            ScenarioEngine(provider).generate(valid_request)
        assert any("meaningfully different" in p for p in exc.value.problems)


class TestSubBranchExpansion:
    def test_expand_alternative_adds_three_children(self, generated_report, mock_engine):
        expanded = mock_engine.expand_branch(generated_report, "alt-1")
        node = next(a for a in expanded["alternatives"] if a["id"] == "alt-1")
        assert len(node["children"]) == 3
        assert [c["id"] for c in node["children"]] == ["alt-1.c1", "alt-1.c2", "alt-1.c3"]
        for child in node["children"]:
            assert child["parent_id"] == "alt-1"
            assert child["triggers"]
        assert validate_report(expanded) == []

    def test_expansion_has_child_comparison(self, generated_report, mock_engine):
        expanded = mock_engine.expand_branch(generated_report, "baseline")
        assert expanded["baseline"]["child_comparison"] is not None
        assert validate_report(expanded) == []

    def test_expand_does_not_mutate_input(self, generated_report, mock_engine):
        original = copy.deepcopy(generated_report)
        mock_engine.expand_branch(generated_report, "alt-2")
        assert generated_report == original

    def test_grandchild_expansion_then_depth_cap(self, generated_report, mock_engine):
        expanded = mock_engine.expand_branch(generated_report, "alt-1")
        deeper = mock_engine.expand_branch(expanded, "alt-1.c1")
        node = next(a for a in deeper["alternatives"] if a["id"] == "alt-1")
        grandchild = node["children"][0]
        assert len(grandchild["children"]) == 3
        assert validate_report(deeper) == []
        with pytest.raises(SchemaValidationError):
            mock_engine.expand_branch(deeper, "alt-1.c1.c1")

    def test_expand_unknown_id(self, generated_report, mock_engine):
        with pytest.raises(SchemaValidationError) as exc:
            mock_engine.expand_branch(generated_report, "alt-99")
        assert any("not found" in p.lower() or "does not exist" in p.lower() for p in exc.value.problems) or "not found" in str(exc.value).lower()

    def test_expand_rejects_invalid_report(self, mock_engine):
        with pytest.raises(SchemaValidationError):
            mock_engine.expand_branch({"schema_version": "1.0.0"}, "alt-1")

    def test_children_titles_are_distinct(self, generated_report, mock_engine):
        expanded = mock_engine.expand_branch(generated_report, "alt-3")
        node = next(a for a in expanded["alternatives"] if a["id"] == "alt-3")
        titles = [c["title"].strip().lower() for c in node["children"]]
        assert len(set(titles)) == 3

    def test_sub_branch_repair_loop(self, generated_report, valid_request):
        children = MockScenarioProvider._children("alt-1", "q")
        broken_children = copy.deepcopy(children)
        broken_children[1]["title"] = broken_children[0]["title"]
        provider = ScriptedProvider(
            [
                {"children": broken_children, "child_comparison": None},
                {"children": children, "child_comparison": None},  # repair
            ]
        )
        expanded = ScenarioEngine(provider).expand_branch(generated_report, "alt-1")
        node = next(a for a in expanded["alternatives"] if a["id"] == "alt-1")
        assert len(node["children"]) == 3
