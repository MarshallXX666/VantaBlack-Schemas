"""StaleMarkRetryState — grouped retry payload for STALE_MARK_RETRYING intents.

Per ADR-0003 §0 vocabulary + user direction (Phase-B ratification
2026-04-21): the four retry-lifecycle fields (retry_count,
first_claim_at, last_claim_at, next_retry_at) form a single
semantic unit — either all None (no retry ever started) or all
populated (retry active/terminated). Nested sub-model models that
invariant directly; flat top-level fields would allow partial
population, which has no meaning.

Matches the existing nested-sub-model precedent in IntentBlock
(EnrichmentData, SanityCheckResult, GateResult).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class StaleMarkRetryState(BaseModel):
    """Retry-lifecycle payload for a STALE_MARK_RETRYING intent.

    Fields:
      - `retry_count`: number of STALE_MARK observations so far, 1-indexed
        (first observation writes retry_count=1, not 0).
      - `first_claim_at`: timestamp of the first STALE_MARK observation.
        Anchors forensics for "how long has this intent been stuck".
      - `last_claim_at`: timestamp of the most recent STALE_MARK
        observation.
      - `next_retry_at`: deadline after which the claimer's next tick
        attempts this intent again. Claimer queries
        `status=STALE_MARK_RETRYING AND next_retry_at <= now()`.

    Populated on the first PENDING_EXECUTION → STALE_MARK_RETRYING
    transition and updated on every subsequent retry attempt.
    Terminal STALE_MARK_RETRY_EXHAUSTED preserves this block as
    forensic payload on the SKIPPED intent.
    """

    retry_count: int
    first_claim_at: datetime
    last_claim_at: datetime
    next_retry_at: datetime

    model_config = ConfigDict(
        frozen=False,
        extra="forbid",
        use_enum_values=False,
    )
