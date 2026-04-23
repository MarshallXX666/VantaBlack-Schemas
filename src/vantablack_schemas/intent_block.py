"""IntentBlock — canonical cross-repo intent model.

Reflects the Phase-B decisions archived at
`VantaBlack-EXE/docs/L2-track-2A-phase-B-decisions.md`:

- D1 = 1A: EXE-style field names (`intent_id`, `created_at`,
  `underlying`). Legacy aliases (`id`, `timestamp`, `ticker`)
  accepted at validation time — time-boxed, removal deadline
  2026-05-10 (see CHANGELOG.md).
- D2 = 2C: typed `EnrichmentData` sub-model; outer
  `extra="forbid"` but `EnrichmentData` has `extra="allow"` as an
  explicit extension point.
- D3 = 3C: unified `IntentLegSpec` (12 execution fields + 5
  Optional market-snapshot fields).
- D4 = 4B: `AliasChoices` for legacy field names; documented with
  removal deadlines.
- D5 = 5B (transitional): `signal_id: Optional[str] = None` in
  v0.1 so legacy docs deserialize; flip to required in v0.2 after
  Core starts writing it and the rewrite-job backfills old docs.

Outer model is `extra="forbid"` — contract discipline rule per
user direction (session 3 close: "contract cannot be an implicit
protocol").

TODO(aliases-remove-after-2026-05-10): remove `AliasChoices(...)`
on intent_id / created_at / underlying; tighten `signal_id` to
required `str`; prune V2-legacy IntentStatus members.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .enrichment import EnrichmentData
from .enums import (
    ExecutionMode,
    IntentDirection,
    IntentState,
    IntentStatus,
    IntentType,
    IVRegime,
    NarrativeType,
    SanityAction,
    StructureType,
    TimeInForce,
)
from .leg import IntentLegSpec
from .retry_state import StaleMarkRetryState


class GateResult(BaseModel):
    """Pre-exec gate result (Core's L1/L2 gate decisions)."""

    passed: bool
    skip_reasons: list[str]
    checked_at: datetime

    model_config = ConfigDict(frozen=True, extra="forbid")


class SanityCheckResult(BaseModel):
    """Core-side sanity check (ratio + action)."""

    ratio: float
    action: SanityAction

    model_config = ConfigDict(frozen=True, extra="forbid")


class IntentBlock(BaseModel):
    """Canonical IntentBlock — shared by Core (writer), EXE (reader +
    executor), PM (reader + outcome).

    Field ordering follows the Phase-A catalog groups: identity,
    timestamps, status/state, mode/type, symbology, sizing, decision,
    legs, dict containers, outcome.
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    intent_id: str = Field(
        validation_alias=AliasChoices("intent_id", "id"),
        description=(
            "Primary key. Legacy alias 'id' accepted for pre-migration "
            "docs — removal deadline 2026-05-10."
        ),
    )
    # TODO(aliases-remove-after-2026-05-10): flip to required `str` in
    # v0.2.0 after Core writer migration + rewrite-job.
    signal_id: Optional[str] = Field(
        default=None,
        description=(
            "Upstream signal identifier. Transitional Optional in v0.1; "
            "Decision D5=5B mandates required+Core-written in v0.2."
        ),
    )
    correlation_id: Optional[str] = None
    chain_id: Optional[str] = None
    parent_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle timestamps
    # ------------------------------------------------------------------
    created_at: datetime = Field(
        validation_alias=AliasChoices("created_at", "timestamp"),
        description=(
            "Intent creation time. Legacy alias 'timestamp' accepted "
            "for pre-migration docs — removal deadline 2026-05-10."
        ),
    )
    created_by: Optional[str] = None
    proposed_at: Optional[datetime] = None
    activated_at: Optional[datetime] = None
    state_updated_at: Optional[datetime] = None
    claimed_at: Optional[datetime] = None
    claimed_by: Optional[str] = None
    terminal_at: Optional[datetime] = None
    terminal_reason: Optional[str] = None

    # ------------------------------------------------------------------
    # STALE_MARK retry lifecycle (ADR-0003 A+B, Schemas v0.1.4)
    #
    # Populated on PENDING_EXECUTION → STALE_MARK_RETRYING transition,
    # updated on every subsequent retry attempt, preserved on
    # STALE_MARK_RETRY_EXHAUSTED terminal SKIPPED for forensics.
    # Invariant: None iff intent has NEVER observed STALE_MARK.
    # ------------------------------------------------------------------
    stale_mark_retry_state: Optional[StaleMarkRetryState] = None

    # ------------------------------------------------------------------
    # Status + state
    # ------------------------------------------------------------------
    status: IntentStatus
    state: Optional[IntentState] = None

    # ------------------------------------------------------------------
    # Mode + intent type (OPEN/CLOSE discriminator)
    # ------------------------------------------------------------------
    execution_mode: Optional[ExecutionMode] = None
    dry_run: Optional[bool] = None
    intent_type: IntentType = IntentType.OPEN
    parent_position_id: Optional[str] = None
    close_qty: Optional[int] = None
    close_reason: Optional[str] = None
    close_intent_ids: Optional[list[str]] = None

    # ------------------------------------------------------------------
    # Symbology + instrument
    # ------------------------------------------------------------------
    underlying: str = Field(
        validation_alias=AliasChoices("underlying", "ticker"),
        description=(
            "Underlying symbol. Legacy alias 'ticker' accepted for "
            "pre-migration docs — removal deadline 2026-05-10."
        ),
    )
    opra_symbol: Optional[str] = None
    tiger_symbol: Optional[str] = None
    symbology_translator_version: Optional[str] = None
    direction: Optional[IntentDirection] = None
    structure_type: Optional[StructureType] = None

    # ------------------------------------------------------------------
    # Sizing (Y5 v2 OPEN)
    # ------------------------------------------------------------------
    schema_version: Optional[int] = 1
    # Y5 Step 6 cross-service sizing contract (ADR Y5 §2.6). Core writes
    # these on v2 OPEN intents; EXE Y5 sizer consumes them at claim time
    # to derive quantity + limit. MUST persist through Firestore round-trip
    # — pre-2026-04-23 comments marked these "ephemeral" which caused
    # intent_store to drop them on write and broke every AUTO flip attempt
    # (EXE saw size_pct=None → SIZE_INVALID_PCT). Optional because CLOSE
    # intents and legacy v1 docs legitimately leave them None.
    size_pct: Optional[float] = None
    slippage_bps: Optional[int] = None
    max_premium_per_contract_s10k: Optional[int] = None
    max_slippage_bps: Optional[int] = None
    quantity: Optional[int] = None
    limit_price_s10k: Optional[int] = None

    # ------------------------------------------------------------------
    # Decision / gate / sanity
    # ------------------------------------------------------------------
    target_delta: Optional[float] = None
    target_dte: Optional[int] = None
    stop_level: Optional[float] = None
    target_level: Optional[float] = None
    l1_gate: Optional[GateResult] = None
    l2_gate: Optional[GateResult] = None
    sanity_check: Optional[SanityCheckResult] = None
    time_in_force: Optional[TimeInForce] = None
    intent_ttl_seconds: Optional[int] = 60

    # ------------------------------------------------------------------
    # Legs
    # ------------------------------------------------------------------
    legs: Optional[list[IntentLegSpec]] = None

    # ------------------------------------------------------------------
    # Market snapshot (top-level — Core writes these flat, NOT inside
    # enrichment_data). Must stay as typed fields for write-path fidelity.
    # ------------------------------------------------------------------
    iv_regime: Optional[IVRegime] = None
    entry_ivPctile1y: Optional[float] = None
    entry_exErnIv20d: Optional[float] = None
    entry_expected_move_pct: Optional[float] = None
    expected_move_pct: Optional[float] = None  # deprecated alias; Core writes both during migration
    expected_holding_days: Optional[int] = None
    entry_slope: Optional[float] = None
    entry_contango: Optional[float] = None
    entry_hv5d_hv20d_ratio: Optional[float] = None
    entry_hv_iv_spread: Optional[float] = None
    entry_stock_price: Optional[float] = None
    scoring_factors: Optional[list[str]] = None
    narrative_type: Optional[NarrativeType] = None
    narrative_source: Optional[str] = None
    narrative_confidence: Optional[float] = None
    signal_source: Optional[str] = None

    # ------------------------------------------------------------------
    # Structure upgrade forensics
    # ------------------------------------------------------------------
    structure_upgraded: Optional[bool] = None
    upgrade_reason: Optional[str] = None
    pre_upgrade_structure: Optional[dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Dict containers (explicit extension points)
    # ------------------------------------------------------------------
    signal_data: Optional[dict[str, Any]] = None
    enrichment_data: Optional[EnrichmentData] = None
    candidates_data: Optional[list[dict[str, Any]]] = None

    # ------------------------------------------------------------------
    # V2-era LLM artifacts (kept for backward compat, Core writes as dict)
    # ------------------------------------------------------------------
    trade_plan: Optional[dict[str, Any]] = None
    cage_result: Optional[dict[str, Any]] = None

    # ------------------------------------------------------------------
    # Outcome (patch-written by Core's update_outcome / update_state)
    # ------------------------------------------------------------------
    entry_fill: Optional[float] = None
    exit_fill: Optional[float] = None
    exit_trigger: Optional[str] = None  # V2 exit rule
    exit_source: Optional[str] = None  # "PM_RULE" | "MANUAL_OVERRIDE" | "REFRESH"
    exit_trigger_v3: Optional[str] = None  # V3 exit rule
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    hold_days: Optional[int] = None
    notes: Optional[str] = None
    actual_fill_price: Optional[float] = None
    actual_qty: Optional[int] = None
    skip_reason: Optional[str] = None
    telegram_message_id: Optional[int] = None
    manual_exit_reason: Optional[str] = None

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------
    model_config = ConfigDict(
        frozen=False,  # Core mutates in-memory during enrichment; PM mutates at exit
        # v0.1.5 (2026-04-23): outer `extra` relaxed to "ignore" for the
        # alias-live-dual-write window. Core's intent_store.save() emits both
        # canonical keys (intent_id/created_at/underlying) AND legacy aliases
        # (id/timestamp/ticker) for back-compat with Core-internal Firestore
        # queries at src/services/intent_store.py:549,605,675-676,873-874.
        # Schemas validating read-side docs must tolerate those legacy extras
        # or the dual-write makes every saved doc unreadable by EXE + PM.
        # Inner sub-models (GateResult/SanityCheckResult/IntentLegSpec) keep
        # extra="forbid" — typos there still fail loudly. Flip back to
        # "forbid" at the 2026-05-10 aliases-removal deadline.
        extra="ignore",  # ← relaxed for dual-write tolerance, see comment
        populate_by_name=True,  # attribute access uses canonical names
        use_enum_values=False,
        arbitrary_types_allowed=False,
    )
