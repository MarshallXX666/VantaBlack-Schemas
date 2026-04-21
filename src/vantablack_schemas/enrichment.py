"""EnrichmentData — typed sub-model for PM's hot-path intent fields.

Per Phase-B D2 = 2C (typed sub-model + nested extra="allow"):

- All PM-consumed fields ARE declared here as typed attributes. This
  catches typos and drift at schema layer rather than at runtime
  attribute access.
- `extra="allow"` permits Core to attach new market-snapshot fields
  without immediately bumping Schemas version. Consumers that want
  to read a new key must promote it to a typed field in a Schemas
  PR first (reviewer gate).

Explicit extension point. The outer `IntentBlock` remains
`extra="forbid"`.

Every field here is Optional because PM tolerates partial
enrichment during degraded paths (e.g. Core fallback narratives).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from .enums import IVRegime, NarrativeType


class EnrichmentData(BaseModel):
    """Decision-time + market-snapshot fields PM reads.

    Inventoried from VantaBlack-PM audit (session 4 Phase A):
    `src/pm/intent_block.py`, `src/pm/decide_v3.py`,
    `src/outcome/tracker.py`, `src/snapshot/collector.py`.
    """

    # Market snapshot at signal time
    iv_regime: Optional[IVRegime] = None
    entry_ivPctile1y: Optional[float] = None
    entry_exErnIv20d: Optional[float] = None
    iv_rank: Optional[float] = None
    entry_stock_price: Optional[float] = None
    current_price: Optional[float] = None

    # Move + hold expectations
    entry_expected_move_pct: Optional[float] = None
    expected_move_pct: Optional[float] = None  # deprecated alias; PM falls back
    expected_holding_days: Optional[int] = None
    trade_stop_level: Optional[float] = None

    # Trade direction + structure
    trade_direction: Optional[str] = None  # "BULL" | "BEAR"
    trade_expiry: Optional[date] = None
    entry_cost: Optional[float] = None

    # Narrative (forensic)
    narrative_type: Optional[NarrativeType] = None
    narrative_source: Optional[str] = None  # "llm" | "fallback"
    scoring_factors: Optional[list[str]] = None

    # V3 decision / sanity
    sanity_ratio: Optional[float] = None
    sanity_check: Optional[dict[str, Any]] = None  # legacy nested-dict (ratio + action); PM reads via (sanity_check or {}).get("ratio")
    tier: Optional[str] = None
    signal_tier: Optional[str] = None
    target_dte: Optional[int] = None
    structure_upgraded: Optional[bool] = None
    refresh_generation: Optional[int] = None
    refresh_count: Optional[int] = None  # legacy alias for refresh_generation; PM reads with fallback chain

    # Legs (PM-side forensic — separate from IntentBlock.legs)
    long_leg: Optional[dict[str, Any]] = None
    short_leg: Optional[dict[str, Any]] = None

    # Post-exit writes (PM daemon fills these at _handle_exit_v3)
    pnl_pct: Optional[float] = None
    exit_fill: Optional[float] = None

    # Position linkage (set by Core's manual_position_opener)
    position_id: Optional[str] = None

    model_config = ConfigDict(
        extra="allow",  # ← explicit extension point, per D2=2C
        use_enum_values=False,
    )
