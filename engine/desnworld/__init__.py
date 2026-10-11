"""
DESNWORLD — a general-purpose AI scenario exploration engine.

DESNWORLD helps users explore possible futures: a baseline scenario, three
alternative branches, the triggers that would select each branch, documented
uncertainties and evidence gaps, and a comparison report. It explores
possibilities — it does not predict the future with certainty.

Derived in part from MiroFish (https://github.com/666ghj/MiroFish), AGPL-3.0.
See NOTICE.md at the repository root for attribution details.
"""

from .engine import ScenarioEngine
from .errors import (
    EngineError,
    InputValidationError,
    MalformedResponseError,
    MissingCredentialsError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
    SchemaValidationError,
)
from .schema import ENGINE_NAME, ENGINE_VERSION, SCHEMA_VERSION

__all__ = [
    "ScenarioEngine",
    "EngineError",
    "InputValidationError",
    "MalformedResponseError",
    "MissingCredentialsError",
    "ProviderError",
    "ProviderTimeoutError",
    "RateLimitError",
    "SchemaValidationError",
    "ENGINE_NAME",
    "ENGINE_VERSION",
    "SCHEMA_VERSION",
]

__version__ = ENGINE_VERSION
