# Changelog

## v0.1.4 — 2026-04-21

### Added

- `IntentStatus.STALE_MARK_RETRYING` — new intermediate state for
  the ADR-0003 A+B retry path. Claimer transitions
  `PENDING_EXECUTION → STALE_MARK_RETRYING` when the sizer observes
  a cold `MarkCache` entry; re-attempts after `next_retry_at`.
  Terminal on retry exhaustion → `SKIPPED` with reason
  `STALE_MARK_RETRY_EXHAUSTED`.
- `StaleMarkRetryState` sub-model — grouped retry-lifecycle payload
  (`retry_count`, `first_claim_at`, `last_claim_at`, `next_retry_at`).
  Either all None (no STALE_MARK ever observed) or all populated.
  Matches the existing nested-sub-model precedent
  (`EnrichmentData`, `SanityCheckResult`, `GateResult`) per user's
  Phase-B ratification nudge.
- `IntentBlock.stale_mark_retry_state: Optional[StaleMarkRetryState]` —
  top-level field carrying the nested payload.

### Non-breaking

All additions are additive. Existing consumers that deserialize
historical docs (where these fields are absent) get `None` and
continue working.

### Rationale

See `VantaBlack-EXE/docs/adr/0003-mark-cache-intent-feed.md` §0 +
§4b for the decision record and payload vocabulary.

## v0.1.3 — 2026-04-21

### Added

- `IVRegime.NORMAL` — V2 legacy enum member retained for backward
  compat with pre-V3 Firestore docs. Surfaced during Core migration
  (4C Step 2): Core's V2 integration tests write `iv_regime="NORMAL"`
  which V3's 4-member enum rejected. Removing in v0.2.0 after
  rewrite-job.
- `StructureType.NAKED_LONG` — V2 legacy (direction-inferred).
  Canonical V3 members are `NAKED_LONG_CALL` / `NAKED_LONG_PUT`.
  Removing in v0.2.0.

### Why additive-only

Both values surfaced from actual pre-V3 Core-written data. Rejecting
them at canonical validation would force a one-shot Firestore
migration before v0.1 could ship — that churn is what D4=4B's
time-boxed aliases explicitly avoid. Additive legacy members behave
identically to the IntentStatus V2-legacy pattern from v0.1.0.

## v0.1.2 — 2026-04-21

### Added

- `vantablack_schemas.fixtures` sub-package — three golden payload
  classes for cross-repo contract testing:
  - `LEGACY_CORE_PAYLOAD` + `legacy_core_payload(**overrides)` —
    pre-2A-rename field names (`id` / `timestamp` / `ticker`),
    exercises the `AliasChoices` migration path consumers see during
    Phase D's alias-live window.
  - `CANONICAL_CORE_PAYLOAD` + `canonical_core_payload(**overrides)` —
    post-rename steady-state shape.
  - `EDGE_CASE_PAYLOADS` — 13 `(name, payload, expect_kind)` tuples
    covering: outer `extra="forbid"`, `EnrichmentData.extra="allow"`,
    required/Optional field cardinality, legacy `IntentStatus` V2
    members, IntentLegSpec `instrument`→`option_type` alias,
    `signal_data` opacity.

Fixtures live inside the installed package (under
`src/vantablack_schemas/fixtures/`) so consumer repos (EXE, PM,
Core) can `from vantablack_schemas.fixtures import ...` without a
separate test-asset distribution.

## v0.1.1 — 2026-04-21

### Added

- `EnrichmentData.sanity_check: Optional[dict[str, Any]]` — legacy
  nested-dict shape `{ratio, action}` that PM reads via the
  `(sanity_check or {}).get("ratio")` idiom during Phase C migration.
  Core's canonical `sanity_check` is a top-level
  `SanityCheckResult`; this EnrichmentData field exists to preserve
  PM's current read path without forcing a simultaneous PM
  refactor to read from top-level. Remove in v0.2.0 after PM
  migrates reads.
- `EnrichmentData.refresh_count: Optional[int]` — legacy alias of
  `refresh_generation`. PM reads both in a fallback chain. Remove
  in v0.2.0.

### Rationale

The two additions are **typed** fields, not dict-compat methods.
Per Phase-B D2=2C discipline, EnrichmentData's only escape hatch
remains `extra="allow"`. These legacy fields become explicit-and-
typed instead of flowing through `extra="allow"`, giving PM
migration a clean target.

## v0.1.0 — 2026-04-21 (initial release)

### Summary

First release of the shared-schemas package for VantaBlack
Core/EXE/PM. Consolidates three previously-divergent `IntentBlock`
classes (one per repo) into a single source of truth.

### Canonical field names

Decisions per L2 Track 2A Phase B (archived in
`VantaBlack-EXE/docs/L2-track-2A-phase-B-decisions.md`):

- `intent_id` (was Core's `id`, EXE/canonical `intent_id`)
- `created_at` (was Core's `timestamp`, EXE/canonical `created_at`)
- `underlying` (was Core's `ticker`, EXE/canonical `underlying`)
- `status` uses `IntentStatus` enum (V3 values) — legacy V2 values
  (`REJECTED`, `PLANNED`, `ENTERED`, `ACTIVE`, `EXITED`) accepted on
  read for backward compat, not written by new code.

### Migration aliases (time-boxed — MUST be removed by 2026-05-10)

The following fields accept legacy names at validation time via
`pydantic.AliasChoices`. Serialization (`.model_dump()`) always
emits the canonical name. Consumers migrate reader call sites to
canonical during the v0.1 window.

| Model | Canonical field | Legacy alias | Used by (legacy) |
|-------|-----------------|--------------|-------------------|
| IntentBlock | intent_id | id | Core writer, PM reader |
| IntentBlock | created_at | timestamp | Core writer, PM reader |
| IntentBlock | underlying | ticker | Core writer, PM reader |
| IntentLegSpec | option_type | instrument | PM reader |

### Escape hatches (non-timeboxed, explicit extension points)

- `EnrichmentData.model_config = ConfigDict(extra="allow")` —
  permits Core to add new V3 market-snapshot fields without
  bumping the Schemas version. All PM-consumed keys ARE typed
  fields inside `EnrichmentData`; the `extra="allow"` is for
  genuinely new additions that no consumer has wired yet. Any PR
  that adds a field PM consumes must TYPE it, not rely on
  `extra="allow"`.
- `IntentBlock.signal_data: dict[str, Any]` — raw signal payload
  from webhooks; opaque by design (consumers extract keys they
  need at read time).

### Transitional `Optional[str]` fields (will tighten in v0.2.0)

- `signal_id: Optional[str] = None` — Decision D5 (Phase B) mandates
  this be required + Core-written. During v0.1 Core migration to
  write it, the field stays Optional to avoid breaking legacy doc
  reads. Flip to `str` (required) in v0.2.0 after Core migration
  lands and rewrite-job backfills legacy docs.

## v0.2.0 — planned 2026-05-10 (tentative)

Blocked on: Core's `intent_store.save()` migration to write new
names + `signal_id`; rewrite-job run on legacy Firestore docs.

Changes:

- Remove all `AliasChoices(...)` entries per table above.
- `signal_id: Optional[str] = None` → `signal_id: str`.
- Drop V2 legacy values (`REJECTED`, `PLANNED`, `ENTERED`,
  `ACTIVE`, `EXITED`) from `IntentStatus` enum.
