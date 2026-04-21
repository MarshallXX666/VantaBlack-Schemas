"""Tests for StaleMarkRetryState + IntentBlock retry-lifecycle integration.

Covers:
- StaleMarkRetryState round-trip (all 4 fields present, all required).
- IntentBlock default: stale_mark_retry_state == None.
- IntentBlock with populated retry state round-trips.
- IntentStatus.STALE_MARK_RETRYING value + membership.
- extra="forbid" on StaleMarkRetryState.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from vantablack_schemas import (
    IntentBlock,
    IntentStatus,
    StaleMarkRetryState,
)
from vantablack_schemas.fixtures import CANONICAL_CORE_PAYLOAD


NOW = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
BACKOFF_DEADLINE = datetime(2026, 4, 21, 12, 1, 5, tzinfo=timezone.utc)


def _retry_state_payload(**overrides) -> dict:
    base = {
        "retry_count": 1,
        "first_claim_at": NOW.isoformat(),
        "last_claim_at": NOW.isoformat(),
        "next_retry_at": BACKOFF_DEADLINE.isoformat(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# StaleMarkRetryState — shape + constraints
# ---------------------------------------------------------------------------

def test_retry_state_all_four_fields_required():
    """Every field is required — no optional/None behavior within the
    nested payload. (Optional lives at the IntentBlock level:
    stale_mark_retry_state is Optional[StaleMarkRetryState].)"""
    full = StaleMarkRetryState.model_validate(_retry_state_payload())
    assert full.retry_count == 1
    assert full.first_claim_at == NOW
    assert full.last_claim_at == NOW
    assert full.next_retry_at == BACKOFF_DEADLINE


@pytest.mark.parametrize("missing", [
    "retry_count", "first_claim_at", "last_claim_at", "next_retry_at",
])
def test_retry_state_rejects_missing_required(missing):
    payload = _retry_state_payload()
    del payload[missing]
    with pytest.raises(ValidationError):
        StaleMarkRetryState.model_validate(payload)


def test_retry_state_extra_forbidden():
    """Nested extra=forbid: no surprise fields smuggled into retry payload."""
    with pytest.raises(ValidationError):
        StaleMarkRetryState.model_validate(
            _retry_state_payload(surprise_field="nope")
        )


def test_retry_state_roundtrip():
    original = StaleMarkRetryState.model_validate(_retry_state_payload(retry_count=3))
    dumped = original.model_dump(mode="json")
    reparsed = StaleMarkRetryState.model_validate(dumped)
    assert reparsed == original


# ---------------------------------------------------------------------------
# IntentStatus enum membership
# ---------------------------------------------------------------------------

def test_intent_status_has_stale_mark_retrying_member():
    assert IntentStatus.STALE_MARK_RETRYING.value == "STALE_MARK_RETRYING"
    assert "STALE_MARK_RETRYING" in {s.value for s in IntentStatus}


def test_intent_block_accepts_stale_mark_retrying_status():
    payload = dict(CANONICAL_CORE_PAYLOAD)
    payload["status"] = "STALE_MARK_RETRYING"
    intent = IntentBlock.model_validate(payload)
    assert intent.status == IntentStatus.STALE_MARK_RETRYING


# ---------------------------------------------------------------------------
# IntentBlock.stale_mark_retry_state integration
# ---------------------------------------------------------------------------

def test_intent_block_default_retry_state_is_none():
    intent = IntentBlock.model_validate(CANONICAL_CORE_PAYLOAD)
    assert intent.stale_mark_retry_state is None


def test_intent_block_with_populated_retry_state_roundtrips():
    payload = dict(CANONICAL_CORE_PAYLOAD)
    payload["status"] = "STALE_MARK_RETRYING"
    payload["stale_mark_retry_state"] = _retry_state_payload(retry_count=2)
    intent = IntentBlock.model_validate(payload)
    assert intent.stale_mark_retry_state is not None
    assert intent.stale_mark_retry_state.retry_count == 2
    assert intent.stale_mark_retry_state.next_retry_at == BACKOFF_DEADLINE

    # Round-trip stability
    redump = intent.model_dump(mode="json")
    reparsed = IntentBlock.model_validate(redump)
    assert reparsed.stale_mark_retry_state == intent.stale_mark_retry_state


def test_intent_block_retry_state_nested_extra_forbidden():
    """Outer IntentBlock extra=forbid + nested retry_state extra=forbid."""
    payload = dict(CANONICAL_CORE_PAYLOAD)
    payload["stale_mark_retry_state"] = _retry_state_payload(unknown="ignored?")
    with pytest.raises(ValidationError):
        IntentBlock.model_validate(payload)


def test_exhausted_terminal_preserves_retry_state_payload():
    """On STALE_MARK_RETRY_EXHAUSTED → SKIPPED, the retry_state block
    stays populated for forensics (user requirement per ADR §0)."""
    payload = dict(CANONICAL_CORE_PAYLOAD)
    payload["status"] = "SKIPPED"
    payload["terminal_reason"] = "STALE_MARK_RETRY_EXHAUSTED"
    payload["stale_mark_retry_state"] = _retry_state_payload(retry_count=3)
    intent = IntentBlock.model_validate(payload)
    assert intent.status == IntentStatus.SKIPPED
    assert intent.terminal_reason == "STALE_MARK_RETRY_EXHAUSTED"
    assert intent.stale_mark_retry_state is not None
    assert intent.stale_mark_retry_state.retry_count == 3
