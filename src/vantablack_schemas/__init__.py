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

__version__ = "0.1.3"

__all__ = [
    # top-level
    "IntentBlock",
    "IntentLegSpec",
    "EnrichmentData",
    "GateResult",
    "SanityCheckResult",
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
