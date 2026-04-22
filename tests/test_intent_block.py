"""Tests for canonical IntentBlock + the time-boxed migration aliases.

Coverage goals:
- Legacy Core-style payload (id/timestamp/ticker) deserializes.
- New V3-style payload (intent_id/created_at/underlying) deserializes.
- Attribute access always uses canonical names.
- `model_dump(by_alias=False)` emits canonical names for both paths.
- Outer `extra="forbid"` rejects undeclared fields.
- `EnrichmentData.extra="allow"` tolerates unknown inner keys.
- `IntentLegSpec.option_type` alias (`instrument`) works.
- Legacy `IntentStatus` V2 values (PLANNED / ENTERED / ...) deserialize.
- `signal_id` transitional: Optional in v0.1 (missing is OK).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from vantablack_schemas import (
    EnrichmentData,
    IntentBlock,
    IntentLegSpec,
    IntentStatus,
    IVRegime,
    LegSide,
    NarrativeType,
    OptionType,
    StructureType,
    TimeInForce,
    Currency,
    MultiplierSource,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)


def _leg_payload(**overrides) -> dict:
    base = {
        "leg_index": 0,
        "side": "BUY",
        "opra_symbol": "AAPL260530C00200000",
        "tiger_symbol": "AAPL 260530C200",
        "strike": 200.0,
        "expiry": "2026-05-30",
        "option_type": "CALL",
        "ratio": 1,
        "multiplier": 100,
        "currency": "USD",
        "multiplier_source": "ORATS",
        "multiplier_fetched_at": NOW.isoformat(),
    }
    base.update(overrides)
    return base


def _core_style_payload(**overrides) -> dict:
    """Legacy Core-written IntentBlock shape (pre-2A rename)."""
    base = {
        # legacy names
        "id": "01KPP7N3LEGACY",
        "timestamp": NOW.isoformat(),
        "ticker": "AAPL",
        # V3 core fields
        "status": "PENDING_EXECUTION",
        "execution_mode": "AUTO",
        "dry_run": True,
        "intent_type": "OPEN",
        "direction": "LONG",
        "structure_type": "NAKED_LONG_CALL",
        "time_in_force": "DAY",
        "schema_version": 2,
        "legs": [_leg_payload()],
    }
    base.update(overrides)
    return base


def _v3_style_payload(**overrides) -> dict:
    """New (canonical) IntentBlock shape."""
    base = {
        "intent_id": "01KPP7N3V3",
        "signal_id": "sig-2026-04-21-aapl",
        "created_at": NOW.isoformat(),
        "underlying": "AAPL",
        "status": "PENDING_EXECUTION",
        "execution_mode": "AUTO",
        "dry_run": True,
        "intent_type": "OPEN",
        "direction": "LONG",
        "structure_type": "NAKED_LONG_CALL",
        "time_in_force": "DAY",
        "schema_version": 2,
        "legs": [_leg_payload()],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Alias behavior (D4 = 4B)
# ---------------------------------------------------------------------------

def test_legacy_core_payload_deserializes_via_aliases():
    intent = IntentBlock.model_validate(_core_style_payload())
    assert intent.intent_id == "01KPP7N3LEGACY"
    assert intent.underlying == "AAPL"
    assert intent.created_at.year == 2026


def test_v3_payload_deserializes_via_canonical_names():
    intent = IntentBlock.model_validate(_v3_style_payload())
    assert intent.intent_id == "01KPP7N3V3"
    assert intent.underlying == "AAPL"


def test_dump_emits_canonical_names_for_legacy_input():
    """Round-trip: legacy input → canonical output. No legacy names leak."""
    intent = IntentBlock.model_validate(_core_style_payload())
    dumped = intent.model_dump(mode="json")
    assert "intent_id" in dumped
    assert "created_at" in dumped
    assert "underlying" in dumped
    # Legacy names must NOT appear in the serialized output
    assert "id" not in dumped or dumped.get("id") is None  # no legacy key
    assert "timestamp" not in dumped
    assert "ticker" not in dumped


def test_roundtrip_equality():
    original = IntentBlock.model_validate(_v3_style_payload())
    dumped = original.model_dump(mode="json")
    reparsed = IntentBlock.model_validate(dumped)
    assert reparsed.intent_id == original.intent_id
    assert reparsed.underlying == original.underlying
    assert reparsed.created_at == original.created_at


# ---------------------------------------------------------------------------
# Contract discipline — outer extra="forbid" (D2 meta)
# ---------------------------------------------------------------------------

def test_outer_extra_ignore_silently_drops_unknown_field():
    """v0.1.5: outer `extra="ignore"` replaces v0.1.4's `"forbid"` for
    the alias-live-dual-write window (see CHANGELOG.md v0.1.5).
    Unknown outer fields are silently dropped instead of raising; inner
    sub-models (GateResult/SanityCheckResult/IntentLegSpec) remain
    extra="forbid"."""
    payload = _v3_style_payload()
    payload["some_future_field_that_doesnt_exist"] = "silently_dropped"
    intent = IntentBlock.model_validate(payload)
    dumped = intent.model_dump(mode="json")
    assert "some_future_field_that_doesnt_exist" not in dumped


# ---------------------------------------------------------------------------
# EnrichmentData extension point — extra="allow" (D2 = 2C)
# ---------------------------------------------------------------------------

def test_enrichment_data_allows_unknown_keys():
    """Explicit escape hatch — Core can ship new fields here
    without bumping Schemas."""
    payload = _v3_style_payload()
    payload["enrichment_data"] = {
        "iv_regime": "WARM",
        "entry_expected_move_pct": 0.024,
        "trade_direction": "BULL",
        # Unknown field — must survive
        "brand_new_v3_field": 42,
    }
    intent = IntentBlock.model_validate(payload)
    assert intent.enrichment_data is not None
    assert intent.enrichment_data.iv_regime == IVRegime.WARM
    # Attribute access for the typed field
    assert intent.enrichment_data.entry_expected_move_pct == 0.024
    # Unknown key survives (extra="allow") via model_extra dict
    assert intent.enrichment_data.model_extra.get("brand_new_v3_field") == 42


# ---------------------------------------------------------------------------
# IntentLegSpec superset (D3 = 3C) + instrument alias
# ---------------------------------------------------------------------------

def test_leg_instrument_alias():
    """PM legacy field `instrument` → canonical `option_type`."""
    leg_data = _leg_payload()
    del leg_data["option_type"]
    leg_data["instrument"] = "CALL"  # legacy name
    leg = IntentLegSpec.model_validate(leg_data)
    assert leg.option_type == OptionType.CALL


def test_leg_market_snapshot_fields_optional():
    """PM's delta/iv/bid/ask/oi are Optional."""
    leg = IntentLegSpec.model_validate(_leg_payload())
    assert leg.delta is None
    assert leg.iv is None
    assert leg.bid is None
    assert leg.ask is None
    assert leg.oi is None


def test_leg_with_full_market_snapshot():
    """PM can populate market-snapshot fields."""
    leg = IntentLegSpec.model_validate(_leg_payload(
        delta=0.45,
        iv=0.38,
        bid=2.10,
        ask=2.15,
        oi=1893,
    ))
    assert leg.delta == 0.45
    assert leg.iv == 0.38


def test_leg_extra_forbidden():
    with pytest.raises(ValidationError):
        IntentLegSpec.model_validate(_leg_payload(garbage_field="nope"))


# ---------------------------------------------------------------------------
# IntentStatus V2 legacy deserialization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("legacy_status", [
    "PLANNED", "ENTERED", "ACTIVE", "EXITED", "REJECTED",
])
def test_legacy_v2_status_deserializes(legacy_status):
    """Old Firestore docs with V2 status strings must read OK."""
    payload = _core_style_payload(status=legacy_status)
    intent = IntentBlock.model_validate(payload)
    assert intent.status == IntentStatus(legacy_status)


# ---------------------------------------------------------------------------
# signal_id transitional state (D5 = 5B, v0.1 Optional)
# ---------------------------------------------------------------------------

def test_signal_id_optional_in_v0_1():
    """v0.1 tolerates missing signal_id for legacy-doc compat. v0.2 will
    require it — see CHANGELOG.md."""
    payload = _v3_style_payload()
    del payload["signal_id"]
    intent = IntentBlock.model_validate(payload)
    assert intent.signal_id is None


def test_signal_id_accepted_when_present():
    payload = _v3_style_payload(signal_id="sig-xyz")
    intent = IntentBlock.model_validate(payload)
    assert intent.signal_id == "sig-xyz"


# ---------------------------------------------------------------------------
# IntentLegSpec type variety (strict enum parsing)
# ---------------------------------------------------------------------------

def test_leg_option_type_enum():
    leg = IntentLegSpec.model_validate(_leg_payload(option_type="PUT"))
    assert leg.option_type == OptionType.PUT


def test_leg_side_enum():
    leg = IntentLegSpec.model_validate(_leg_payload(side="SELL"))
    assert leg.side == LegSide.SELL


def test_leg_currency_enum():
    leg = IntentLegSpec.model_validate(_leg_payload(currency="HKD"))
    assert leg.currency == Currency.HKD


# ---------------------------------------------------------------------------
# End-to-end 3-repo contract scenario
# ---------------------------------------------------------------------------

def test_enrichment_legacy_refresh_fallback_chain():
    """v0.1.1: refresh_count present alongside refresh_generation — PM's
    fallback-chain read pattern works on typed attributes."""
    ed = EnrichmentData.model_validate({
        "refresh_generation": None,
        "refresh_count": 3,
    })
    # PM's read pattern: `ed.refresh_generation or ed.refresh_count`
    assert (ed.refresh_generation or ed.refresh_count) == 3


def test_enrichment_legacy_sanity_check_nested_dict():
    """v0.1.1: sanity_check as typed Optional[dict] preserves PM's
    (sanity_check or {}).get('ratio') idiom without dict-compat."""
    ed = EnrichmentData.model_validate({
        "sanity_check": {"ratio": 1.25, "action": "NORMAL"},
    })
    assert (ed.sanity_check or {}).get("ratio") == 1.25
    # Missing case → typed attribute is None
    ed_empty = EnrichmentData.model_validate({})
    assert (ed_empty.sanity_check or {}).get("ratio") is None


def test_three_way_contract_scenario():
    """Simulates Core write → Firestore → EXE read + PM read.

    This is the failure mode that surfaced in incident-01 — Core
    wrote a doc that EXE could not deserialize. With canonical
    IntentBlock, both EXE and PM share the same model.
    """
    # Core writes (mixed legacy + V3 shape, typical transition-window doc)
    core_written = {
        "id": "01KTR3WRITE",  # legacy: Core hasn't migrated writer yet
        "timestamp": NOW.isoformat(),
        "ticker": "NVDA",
        "signal_id": "sig-nvda-breakout-001",
        "status": "PENDING_EXECUTION",
        "execution_mode": "AUTO",
        "dry_run": True,
        "intent_type": "OPEN",
        "direction": "LONG",
        "structure_type": "NAKED_LONG_CALL",
        "time_in_force": "DAY",
        "schema_version": 2,
        "legs": [_leg_payload(opra_symbol="NVDA260530C00500000", tiger_symbol="NVDA 260530C500")],
        "iv_regime": "HOT",
        "entry_expected_move_pct": 0.035,
        "enrichment_data": {
            "iv_regime": "HOT",  # duplicated top-level (both paths populated)
            "trade_direction": "BULL",
            "entry_expected_move_pct": 0.035,
            "narrative_type": "TECHNICAL_BREAKOUT",
            "scoring_factors": ["E_SLOPE_CONFIRM"],
            # Future Core field — extra=allow saves us
            "hypothetical_v3_feature": "future_value",
        },
    }

    # EXE-style read (what execution/intent_claimer.py consumes)
    exe_view = IntentBlock.model_validate(core_written)
    assert exe_view.intent_id == "01KTR3WRITE"
    assert exe_view.underlying == "NVDA"
    assert exe_view.legs is not None
    assert exe_view.legs[0].multiplier == 100  # precheck rule 1 gate
    assert exe_view.time_in_force == TimeInForce.DAY  # precheck rule 4 gate

    # PM-style read (what src/pm/decide_v3.py + outcome/tracker.py need)
    pm_view = IntentBlock.model_validate(core_written)
    assert pm_view.enrichment_data is not None
    assert pm_view.enrichment_data.trade_direction == "BULL"
    assert pm_view.enrichment_data.entry_expected_move_pct == 0.035
    assert pm_view.enrichment_data.narrative_type == NarrativeType.TECHNICAL_BREAKOUT
    assert pm_view.enrichment_data.scoring_factors == ["E_SLOPE_CONFIRM"]
    # PM tolerates future fields at enrichment layer
    assert (
        pm_view.enrichment_data.model_extra.get("hypothetical_v3_feature")
        == "future_value"
    )

    # Both views round-trip to the SAME canonical shape
    assert exe_view.model_dump(mode="json") == pm_view.model_dump(mode="json")
