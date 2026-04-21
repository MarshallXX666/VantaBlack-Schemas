# Changelog

## v0.1.0 — 2026-04-21 (planned initial release)

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
