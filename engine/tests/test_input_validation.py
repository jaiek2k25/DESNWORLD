"""Input validation tests: question, domain, horizon, evidence."""

from __future__ import annotations

import pytest

from desnworld.errors import InputValidationError
from desnworld.input_validation import (
    horizon_label,
    normalize_domain,
    request_from_mapping,
    validate_request,
)


class TestQuestion:
    def test_valid_question_is_normalized(self):
        req = validate_request("   How might\t AI regulation \n affect markets?  ", "general", 12)
        assert req["question"] == "How might AI regulation affect markets?"

    def test_question_too_short(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request("Too short", "general", 12)
        assert any("question" in p for p in exc.value.problems)

    def test_question_wrong_type(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request(123, "general", 12)
        assert any("question" in p for p in exc.value.problems)

    def test_question_too_long(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request("x" * 5000, "general", 12, max_question_length=100)
        assert any("at most" in p for p in exc.value.problems)


class TestDomain:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("general", "general"),
            ("General", "general"),
            ("stock_market_education", "stock_market_education"),
            ("Stock Market Education", "stock_market_education"),
            ("stock-market-education", "stock_market_education"),
            ("business", "business"),
            ("Technology", "technology"),
            ("tech", "technology"),
        ],
    )
    def test_aliases(self, raw, expected):
        assert normalize_domain(raw) == expected

    def test_unknown_domain(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request("A perfectly reasonable question here", "underwater basket weaving", 12)
        assert any("domain" in p for p in exc.value.problems)


class TestHorizon:
    @pytest.mark.parametrize("months", [1, 6, 12, 36, 120])
    def test_valid_horizons(self, months):
        req = validate_request("A perfectly reasonable question here", "general", months)
        assert req["horizon"]["months"] == months

    def test_horizon_string_digits_are_accepted(self):
        req = validate_request("A perfectly reasonable question here", "general", "24")
        assert req["horizon"]["months"] == 24

    @pytest.mark.parametrize("months", [0, -3, 121, 1000])
    def test_out_of_range(self, months):
        with pytest.raises(InputValidationError) as exc:
            validate_request("A perfectly reasonable question here", "general", months)
        assert any("horizon_months" in p for p in exc.value.problems)

    def test_non_integer(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request("A perfectly reasonable question here", "general", "soon")
        assert any("horizon_months" in p for p in exc.value.problems)

    def test_boolean_is_rejected(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request("A perfectly reasonable question here", "general", True)
        assert any("horizon_months" in p for p in exc.value.problems)

    @pytest.mark.parametrize(
        "months,label",
        [(1, "1 month"), (3, "3 months"), (12, "1 year"), (18, "1 year 6 months"), (24, "2 years")],
    )
    def test_horizon_labels(self, months, label):
        assert horizon_label(months) == label


class TestEvidence:
    def test_string_items_are_accepted(self):
        req = validate_request(
            "A perfectly reasonable question here",
            "general",
            12,
            evidence=["A simple evidence note"],
        )
        assert req["evidence"][0]["kind"] == "user_supplied_fact"
        assert req["evidence"][0]["id"] == "e1"

    def test_sourced_fact_requires_uri(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request(
                "A perfectly reasonable question here",
                "general",
                12,
                evidence=[{"text": "A claim that pretends to be sourced.", "kind": "sourced_fact"}],
            )
        assert any("source_uri" in p for p in exc.value.problems)

    def test_sourced_fact_with_uri_is_accepted(self):
        req = validate_request(
            "A perfectly reasonable question here",
            "general",
            12,
            evidence=[
                {
                    "text": "A properly sourced claim.",
                    "kind": "sourced_fact",
                    "source_uri": "https://example.com/data",
                }
            ],
        )
        assert req["evidence"][0]["source_uri"] == "https://example.com/data"

    def test_invalid_url(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request(
                "A perfectly reasonable question here",
                "general",
                12,
                evidence=[{"text": "Claim with a bogus URL.", "source_uri": "not-a-url"}],
            )
        assert any("source_uri" in p for p in exc.value.problems)

    def test_too_many_items(self):
        items = [{"text": f"Evidence item number {i}"} for i in range(30)]
        with pytest.raises(InputValidationError) as exc:
            validate_request(
                "A perfectly reasonable question here",
                "general",
                12,
                evidence=items,
                max_evidence_items=20,
            )
        assert any("at most 20" in p for p in exc.value.problems)

    def test_short_evidence_text(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request(
                "A perfectly reasonable question here",
                "general",
                12,
                evidence=[{"text": "x"}],
            )
        assert any("evidence[0].text" in p for p in exc.value.problems)

    def test_malformed_evidence_structure(self):
        with pytest.raises(InputValidationError) as exc:
            validate_request(
                "A perfectly reasonable question here",
                "general",
                12,
                evidence=[42],
            )
        assert any("evidence[0]" in p for p in exc.value.problems)


class TestRequestFromMapping:
    def test_mapping_with_horizon_months(self):
        req = request_from_mapping(
            {
                "question": "A perfectly reasonable question here",
                "domain": "business",
                "horizon_months": 6,
            }
        )
        assert req["domain"] == "business"
        assert req["horizon"] == {"months": 6, "label": "6 months"}

    def test_mapping_collects_all_problems(self):
        with pytest.raises(InputValidationError) as exc:
            request_from_mapping({"question": "short", "domain": "nope", "horizon_months": 0})
        assert len(exc.value.problems) >= 3

    def test_non_object_payload(self):
        with pytest.raises(InputValidationError):
            request_from_mapping(["not", "a", "dict"])  # type: ignore[arg-type]

    def test_error_payload_shape(self):
        with pytest.raises(InputValidationError) as exc:
            request_from_mapping({})
        payload = exc.value.to_payload()
        assert payload["error"] == "input_validation_error"
        assert payload["problems"]
        assert payload["hint"]
