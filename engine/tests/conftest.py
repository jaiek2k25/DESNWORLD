"""Shared fixtures for the DESNWORLD engine test suite."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the engine package importable without installation.
ENGINE_DIR = Path(__file__).resolve().parents[1]
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from desnworld.engine import ScenarioEngine  # noqa: E402
from desnworld.providers import MockScenarioProvider  # noqa: E402


@pytest.fixture()
def valid_request() -> dict:
    return {
        "question": "How might AI regulation affect semiconductor stocks over the next year?",
        "domain": "stock_market_education",
        "horizon_months": 12,
        "evidence": [
            {
                "text": "Recent commentary focuses on how sensitive equity valuations are to rate expectations.",
                "kind": "user_supplied_fact",
            },
            {
                "text": "Historical background on the 2022 inflation surge (educational context).",
                "kind": "sourced_fact",
                "source_uri": "https://en.wikipedia.org/wiki/2021%E2%80%932023_inflation_surge",
            },
        ],
    }


@pytest.fixture()
def mock_engine() -> ScenarioEngine:
    return ScenarioEngine(MockScenarioProvider(), market_data_checked=False)


@pytest.fixture()
def generated_report(mock_engine, valid_request) -> dict:
    return mock_engine.generate(valid_request)
