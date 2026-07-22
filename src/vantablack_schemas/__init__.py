"""vantablack-schemas — shared Pydantic models for Core / EXE / PM.

Primary export: `IntentBlock`. See README.md for install + usage.
"""

from __future__ import annotations

from .enrichment import EnrichmentData
from .enums import (
    Currency,
    ExecutionMode,
    IntentDirection,
    IntentState,
    IntentStatus,
    IntentType,
    IVRegime,
    LegSide,
    MultiplierSource,
    NarrativeType,
    OptionType,
    SanityAction,
    StructureType,
    TimeInForce,
)
from .intent_block import GateResult, IntentBlock, SanityCheckResult
from .leg import IntentLegSpec
from .retry_state import StaleMarkRetryState
from .strategy_engine_wire import (
    STRATEGY_ENGINE_CONTRACT_NAMES,
    STRATEGY_ENGINE_WIRE_VERSION,
    StrategyEngineWireIntegrityError,
    StrategyEngineWireSchemaError,
    canonical_strategy_engine_payload_hash,
    validate_strategy_engine_wire_message,
    verify_strategy_engine_wire_integrity,
)

__version__ = "0.1.6"

__all__ = [
    # top-level
    "IntentBlock",
    "IntentLegSpec",
    "EnrichmentData",
    "GateResult",
    "SanityCheckResult",
    "StaleMarkRetryState",
    "STRATEGY_ENGINE_CONTRACT_NAMES",
    "STRATEGY_ENGINE_WIRE_VERSION",
    "StrategyEngineWireIntegrityError",
    "StrategyEngineWireSchemaError",
    "canonical_strategy_engine_payload_hash",
    "validate_strategy_engine_wire_message",
    "verify_strategy_engine_wire_integrity",
    # enums
    "IntentStatus",
    "IntentState",
    "IntentType",
    "ExecutionMode",
    "IntentDirection",
    "StructureType",
    "TimeInForce",
    "IVRegime",
    "NarrativeType",
    "SanityAction",
    "LegSide",
    "OptionType",
    "Currency",
    "MultiplierSource",
    # metadata
    "__version__",
]
