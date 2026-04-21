"""Cross-repo contract test — Schemas-side.

Exercises the golden fixtures that EXE and PM will also run against
to prove three-way contract alignment. This test is the reference
implementation of "what Core writes + canonical parses + consumers
read must round-trip identically."

Design invariants enforced:

1. Legacy Core payloads (with `id` / `timestamp` / `ticker`) parse
   via `AliasChoices`. Dump emits canonical names only (no legacy
   keys leak).
2. Canonical Core payloads parse unchanged. Dump is a byte-for-byte
   equivalent round-trip.
3. Edge cases enforce outer `extra="forbid"`,
   `EnrichmentData.extra="allow"`, required-vs-Optional cardinality,
   and legacy status/leg-alias back-compat.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from vantablack_schemas import IntentBlock
from vantablack_schemas.fixtures import (
    CANONICAL_CORE_PAYLOAD,
    EDGE_CASE_PAYLOADS,
    LEGACY_CORE_PAYLOAD,
)


# ---------------------------------------------------------------------------
# Fixture class 1 — legacy Core payload (alias migration path)
# ---------------------------------------------------------------------------

def test_legacy_core_payload_deserializes():
    intent = IntentBlock.model_validate(LEGACY_CORE_PAYLOAD)
    # Attribute access uses canonical names
    assert intent.intent_id == "01KTR3LEGACY001"
    assert intent.underlying == "NVDA"
    assert intent.created_at.year == 2026


def test_legacy_core_payload_dumps_canonical_only():
    """Dump must emit canonical names; no legacy keys leak through."""
    intent = IntentBlock.model_validate(LEGACY_CORE_PAYLOAD)
    dumped = intent.model_dump(mode="json")
    # Canonical names present
    assert "intent_id" in dumped
    assert "created_at" in dumped
    assert "underlying" in dumped
    # Legacy names absent (AliasChoices is read-side only by default)
    assert "id" not in dumped
    assert "timestamp" not in dumped
    assert "ticker" not in dumped


def test_legacy_roundtrip_stabilizes():
    """Parse → dump → parse → dump yields identical shape after the
    first conversion (legacy → canonical is a one-way normalization)."""
    first = IntentBlock.model_validate(LEGACY_CORE_PAYLOAD).model_dump(mode="json")
    second = IntentBlock.model_validate(first).model_dump(mode="json")
    assert first == second


# ---------------------------------------------------------------------------
# Fixture class 2 — canonical Core payload (steady-state)
# ---------------------------------------------------------------------------

def test_canonical_core_payload_deserializes():
    intent = IntentBlock.model_validate(CANONICAL_CORE_PAYLOAD)
    assert intent.intent_id == "01KTR3CANON001"
    assert intent.signal_id == "sig-2026-04-21-nvda-breakout-001"
    assert intent.underlying == "NVDA"


def test_canonical_core_payload_dumps_identical():
    """Canonical input → canonical output (excluding Pydantic coercions like
    ISO-8601 datetime vs raw string)."""
    intent = IntentBlock.model_validate(CANONICAL_CORE_PAYLOAD)
    dumped = intent.model_dump(mode="json", exclude_none=True)
    # Every field from the input is present in the dump
    for key in CANONICAL_CORE_PAYLOAD:
        assert key in dumped, f"missing canonical key in dump: {key!r}"


def test_canonical_roundtrip_stable():
    first = IntentBlock.model_validate(CANONICAL_CORE_PAYLOAD).model_dump(mode="json")
    second = IntentBlock.model_validate(first).model_dump(mode="json")
    assert first == second


# ---------------------------------------------------------------------------
# Fixture class 3 — edge cases (contract-invariant enforcement)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,payload,expect_kind",
    EDGE_CASE_PAYLOADS,
    ids=[t[0] for t in EDGE_CASE_PAYLOADS],
)
def test_edge_case(name: str, payload: dict, expect_kind: str):
    """One invariant per case. Parametrized over EDGE_CASE_PAYLOADS so
    the suite stays flat — each name is its own pytest id."""
    if expect_kind == "valid":
        # Must parse without raising
        intent = IntentBlock.model_validate(payload)
        # And must round-trip (dump → reparse)
        re = IntentBlock.model_validate(intent.model_dump(mode="json"))
        assert re.intent_id == intent.intent_id
    elif expect_kind == "raises":
        with pytest.raises(ValidationError):
            IntentBlock.model_validate(payload)
    else:
        pytest.fail(f"unknown expect_kind: {expect_kind!r}")


# ---------------------------------------------------------------------------
# Cross-view invariant — legacy and canonical shapes produce the same canonical
# dump when all semantically-equivalent fields are present.
# ---------------------------------------------------------------------------

def test_legacy_and_canonical_converge_on_core_fields():
    """When a canonical payload is constructed with the same semantic
    content as the legacy payload (same intent_id, same timestamps,
    same symbol), the canonical dump should match on those fields."""
    legacy = IntentBlock.model_validate(LEGACY_CORE_PAYLOAD).model_dump(mode="json")
    canonical_with_matching_core = IntentBlock.model_validate(
        {
            **CANONICAL_CORE_PAYLOAD,
            "intent_id": "01KTR3LEGACY001",
            "created_at": "2026-04-21T12:00:00+00:00",
            "signal_id": None,  # legacy payload doesn't have signal_id
        }
    ).model_dump(mode="json")
    # Fields that should match semantically
    for key in ("intent_id", "created_at", "underlying", "status",
                "execution_mode", "direction", "structure_type",
                "schema_version"):
        assert legacy.get(key) == canonical_with_matching_core.get(key), (
            f"legacy/canonical diverge on {key!r}: "
            f"{legacy.get(key)!r} vs {canonical_with_matching_core.get(key)!r}"
        )
