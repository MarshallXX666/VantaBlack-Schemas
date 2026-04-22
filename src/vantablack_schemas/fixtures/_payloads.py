"""Golden payload fixtures for cross-repo contract tests.

Design:

- **LEGACY_CORE_PAYLOAD**: simulates a Core-written Firestore
  `intents/` doc using the pre-2A-rename field names (`id`,
  `timestamp`, `ticker`, plus Core's legacy status Literal values).
  Exercises the `AliasChoices` migration path in canonical
  IntentBlock. Validates that consumers with v0.1.x can still read
  historical docs during the alias-live deploy window (Phase D).
- **CANONICAL_CORE_PAYLOAD**: simulates a Core-written doc AFTER
  Core's writer migration (new names: `intent_id`, `created_at`,
  `underlying`). Represents the steady-state post-Phase-D.
- **EDGE_CASE_PAYLOADS**: a list of (name, payload, expect_kind)
  tuples. `expect_kind` is one of:
    - `"valid"`: IntentBlock.model_validate succeeds.
    - `"raises"`: model_validate raises ValidationError.
  Each case covers one contract invariant:
    - outer `extra="forbid"` rejects undeclared fields
    - `EnrichmentData.extra="allow"` tolerates unknown keys
    - required fields missing → rejected
    - Optional fields missing → accepted
    - status legacy V2 values → accepted (retained for backward compat)

Consumers use these fixtures to prove their `model_validate` +
`model_dump` path matches the contract without taking a dependency
on Core's internal pipeline.
"""
from __future__ import annotations

from typing import Any

# Frozen timestamp so cross-repo tests compare byte-identical output.
_T = "2026-04-21T12:00:00+00:00"
_EXPIRY = "2026-05-30"


def _leg_payload(**overrides: Any) -> dict:
    base = {
        "leg_index": 0,
        "side": "BUY",
        "opra_symbol": "NVDA260530C00500000",
        "tiger_symbol": "NVDA 260530C500",
        "strike": 500.0,
        "expiry": _EXPIRY,
        "option_type": "CALL",
        "ratio": 1,
        "multiplier": 100,
        "currency": "USD",
        "multiplier_source": "ORATS",
        "multiplier_fetched_at": _T,
    }
    base.update(overrides)
    return base


def legacy_core_payload(**overrides: Any) -> dict:
    """Core-style intent as written BEFORE the Track 2A rename.

    Uses legacy field names (`id`, `timestamp`, `ticker`) that the
    canonical IntentBlock accepts via `AliasChoices`. Kept tight to
    the 11 fields a realistic pre-rename Core doc has — consumers
    don't need the full 75-field shape to prove alias correctness.
    """
    base = {
        # Legacy names — aliased to canonical
        "id": "01KTR3LEGACY001",
        "timestamp": _T,
        "ticker": "NVDA",
        # V3 status (new enum) — Core wrote V3 lifecycle even with
        # legacy field names during the transition window
        "status": "PENDING_EXECUTION",
        "execution_mode": "AUTO",
        "dry_run": True,
        "intent_type": "OPEN",
        "direction": "LONG",
        "structure_type": "NAKED_LONG_CALL",
        "time_in_force": "DAY",
        "schema_version": 2,
        "legs": [_leg_payload()],
        # Enrichment-heavy path (typical Core write)
        "enrichment_data": {
            "iv_regime": "HOT",
            "trade_direction": "BULL",
            "entry_expected_move_pct": 0.035,
            "expected_holding_days": 5,
            "narrative_type": "TECHNICAL_BREAKOUT",
            "scoring_factors": ["E_SLOPE_CONFIRM"],
            "entry_stock_price": 500.0,
        },
    }
    base.update(overrides)
    return base


def canonical_core_payload(**overrides: Any) -> dict:
    """Core-style intent as written AFTER the rename. Steady-state."""
    base = {
        "intent_id": "01KTR3CANON001",
        "signal_id": "sig-2026-04-21-nvda-breakout-001",
        "created_at": _T,
        "underlying": "NVDA",
        "status": "PENDING_EXECUTION",
        "execution_mode": "AUTO",
        "dry_run": True,
        "intent_type": "OPEN",
        "direction": "LONG",
        "structure_type": "NAKED_LONG_CALL",
        "time_in_force": "DAY",
        "schema_version": 2,
        "legs": [_leg_payload()],
        "iv_regime": "HOT",
        "entry_expected_move_pct": 0.035,
        "enrichment_data": {
            "iv_regime": "HOT",
            "trade_direction": "BULL",
            "entry_expected_move_pct": 0.035,
            "expected_holding_days": 5,
            "narrative_type": "TECHNICAL_BREAKOUT",
            "scoring_factors": ["E_SLOPE_CONFIRM"],
            "entry_stock_price": 500.0,
        },
    }
    base.update(overrides)
    return base


# Realised constants (stable across calls — safe for direct use).
LEGACY_CORE_PAYLOAD: dict = legacy_core_payload()
CANONICAL_CORE_PAYLOAD: dict = canonical_core_payload()


# ---------------------------------------------------------------------------
# Edge-case fixtures — each tuple: (name, payload, expect_kind)
# expect_kind ∈ {"valid", "raises"}
# ---------------------------------------------------------------------------
EDGE_CASE_PAYLOADS: list[tuple[str, dict, str]] = [
    (
        "enrichment_extra_allow",
        canonical_core_payload(
            enrichment_data={
                "trade_direction": "BULL",
                "brand_new_v3_field_not_yet_in_schema": 42,
            },
        ),
        "valid",  # extra="allow" on EnrichmentData → unknown key survives
    ),
    (
        "outer_extra_ignore",
        {
            **canonical_core_payload(),
            "totally_undeclared_top_level_field": "silently_dropped",
        },
        # v0.1.5: outer extra relaxed from "forbid" to "ignore" for alias-
        # live-dual-write tolerance (see CHANGELOG.md v0.1.5). Extra keys on
        # the outer model are silently dropped instead of raising. Flip
        # back to "forbid" + "raises" at 2026-05-10 aliases-removal.
        "valid",
    ),
    (
        "required_intent_id_missing",
        {k: v for k, v in canonical_core_payload().items() if k != "intent_id"},
        "raises",  # intent_id (via alias) is required
    ),
    (
        "required_created_at_missing",
        {k: v for k, v in canonical_core_payload().items() if k != "created_at"},
        "raises",
    ),
    (
        "required_underlying_missing",
        {k: v for k, v in canonical_core_payload().items() if k != "underlying"},
        "raises",
    ),
    (
        "required_status_missing",
        {k: v for k, v in canonical_core_payload().items() if k != "status"},
        "raises",
    ),
    (
        "optional_signal_id_missing_v0_1",
        {k: v for k, v in canonical_core_payload().items() if k != "signal_id"},
        "valid",  # signal_id is transitional Optional in v0.1
    ),
    (
        "optional_correlation_id_missing",
        {k: v for k, v in canonical_core_payload().items() if k != "correlation_id"},
        "valid",  # correlation_id is always Optional
    ),
    (
        "legacy_status_v2_planned_accepted",
        canonical_core_payload(status="PLANNED"),
        "valid",  # V2 legacy IntentStatus member retained for backward compat
    ),
    (
        "legacy_status_v2_entered_accepted",
        canonical_core_payload(status="ENTERED"),
        "valid",
    ),
    (
        "signal_data_raw_dict_opaque",
        canonical_core_payload(
            signal_data={"arbitrary_key": 1, "nested": {"anything": "ok"}},
        ),
        "valid",  # signal_data is `dict[str, Any]` — fully opaque
    ),
    (
        "leg_instrument_alias_for_option_type",
        canonical_core_payload(
            legs=[
                {
                    **{k: v for k, v in _leg_payload().items() if k != "option_type"},
                    "instrument": "PUT",  # legacy PM name → aliased to option_type
                }
            ],
        ),
        "valid",
    ),
    (
        "leg_invalid_extra_field_rejected",
        canonical_core_payload(
            legs=[{**_leg_payload(), "surprise_field": "nope"}],
        ),
        "raises",  # IntentLegSpec is extra="forbid"
    ),
]
