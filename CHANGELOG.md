# Changelog

## v0.1.7 — 2026-05-01

### Added

- `contracts/state_transition_event.v1.schema.json`: re-synced from
  VantaBlack-Engine after the lifecycle-setup-types feature merge plus a
  follow-up 7-fix code-review batch + this PR's review-driven hardening
  (Engine commit, deployed as Cloud Run revision `signal-engine-00027-p26`).

  Three new `$defs` (LifecycleStage, SetupType, SetupTag) plus two new
  fields on `StateTransitionEvent`:
  - `setup_composition: list[SetupTag]` — lifecycle setup tags per
    `strategy_synthesis_design.md` §3.1-3.2. Each tag carries `name`
    (one of `breakout` / `pullback_resume` / `reversal_start` /
    `persistent_momentum`), `direction`, and `live_status`. Tags with
    `live_status=False` are SHADOW components per §2.4 — Decision
    Boundary on the consumer side MUST filter them out before sizing.
  - `lifecycle_stage: LifecycleStage` — trend lifecycle phase inferred
    for the event. Defaults to `Unknown` per §2.4 rule #2: while the
    `ongoing` classifier (persistent_momentum) is shadow, Signal Engine
    cannot definitively assert non-`Unknown`. Consumers MUST fail-loud
    on `Unknown` per §2.4 rule #4 — no silent coercion.

- `data/contract_specimens/state_transition_event_v1_specimens.jsonl`:
  expanded from 6 → 13 specimens to address the test gap on positive
  coverage of v0.1.7 fields and the wire-omission shape.

  v0.1.6 baseline (unchanged labels): `long_pass_shadow_a`,
  `short_pass_shadow_a`, `long_fail_low_confidence`,
  `short_fail_multi_reason`, `calibration_phase_new_provider`,
  `post_cutover_live_b`.

  v0.1.7 positive coverage (new): `breakout_birth_long`,
  `pullback_resume_re_entry_short`, `reversal_start_reversal_long`,
  `pullback_resume_with_breakout_compositional`,
  `persistent_momentum_shadow_long`,
  `persistent_momentum_post_promotion_ongoing` (forward-prep for the
  post-shadow regime).

  v0.1.7 wire-omission (new): `wire_default_omitted` — mirrors the
  WebhookDispatcher's actual JSON output when both v0.1.7 fields are
  at default (the dispatcher OMITS them entirely, not just emits the
  default value). Without this specimen the corpus would only cover
  the explicit-default shape, not the wire-omitted shape that strict
  v1 consumers actually see.

### Strengthened (review-driven)

- **`SetupTag.live_status` is now REQUIRED** in the schema (no default).
  Defaulting to `True` silently coerces shadow components into live ones
  if a producer forgets to set it — exactly the §2.4 shadow-isolation
  hole this requirement closes. Engine's existing producer code
  (`SuperTrendProvider._classify_setup_composition`) already sets it
  explicitly for all four setup types, so this is a contract-tightening,
  not a behavior change.

- **Cross-field invariants** documented + enforced via specimens (the
  schema deliberately stays permissive; consumers + specimens carry the
  invariants):
  - `setup_composition[*].direction` MUST equal the event's `direction`
    (consumer-enforced; specimen-locked via
    `test_setup_tag_invariants_within_specimens`).
  - `persistent_momentum` tags MUST have `live_status=False` while the
    ongoing classifier is in shadow phase (§2.4 rule #2). The
    `persistent_momentum_post_promotion_ongoing` specimen is the sole
    documented exception — it represents the post-promotion regime.
  - §3.2 mutex: `persistent_momentum` MUST NOT co-occur with
    `reversal_start` (HTF mutex contradicts persistent's HTF-aligned
    requirement). Engine's classifier suppresses this composition;
    no specimen exercises the forbidden combination.

### Wire compatibility (v1 consumers)

`setup_composition` and `lifecycle_stage` are EMITTED ONLY when their
content is non-default — Signal Engine's `WebhookDispatcher` excludes
them from the JSON payload when (a) `setup_composition` is empty or (b)
`lifecycle_stage == Unknown`. Strict v1 parsers (`extra="forbid"`) on
events with no setup classification continue to see the original v1
shape and accept them. The new `wire_default_omitted` specimen locks
this behavior into the contract corpus.

Consumers that want to react to the new fields should opt in by
widening their parser. SetupTag MUST be parsed strictly
(`extra="forbid"` equivalent in your stack) since its required-fields
list is now load-bearing.

### Documented (was previously unspoken)

- **`event_id`** is a UUID4 emitted on every event for consumer-side
  retry deduplication. Engine's `WebhookDispatcher` retries the same
  payload (with the same `event_id`) up to 5 times with exponential
  backoff on transient consumer 5xx; consumers MUST treat repeat
  `event_id` as the same event and not double-process. Note: across
  Engine restarts the same logical event will get a new UUID4, so
  consumers should ALSO derive a deterministic dedup key from
  `(ticker, bar_close_timestamp_utc, provider_name)` for restart-safe
  idempotency.
- All specimens carry `event_id`; the field has been on the schema
  since v0.1.6 but was not previously called out here.

### Migration notes

- No schema version bump (still `v1`) — additive fields + a tightened
  required list on the v0.1.7-introduced `SetupTag`. Pre-v0.1.7 events
  cannot fail the new `live_status` requirement because they did not
  carry `setup_composition` at all.
- Consumer integration order: VantaBlack-Schemas v0.1.7 (this release) →
  VantaBlack-Core Stage 2 wiring (post 24h soak PASS) → VantaBlack-PM
  Stage 3 wiring (post cut-over).

## v0.1.6 — 2026-04-27

### Added

- `IntentBlock.signal_source`: type tightened from `Optional[str] = None`
  to `str = Field(default="tv_legacy")`. Enables multi-provider future
  per `engine_adaptation_design.md` §3.3 + `core_cc_proposal_final.md`
  §3.S1.1. Vocabulary:
  - `"SuperTrend_v2"` — Signal Engine path (Stage 2+)
  - `"tv_legacy"` — TV path or backfilled records (default for missing)
  - `"L1_FLIP"` / `"IV_CONTINUATION"` — legacy values retained for
    forensic-query compatibility on pre-v0.1.6 docs
  - Future: `"CVOL_PVOL_v1"`, `"MR_v1"`, etc.
- `IntentBlock.entry_provider_context`: new `Optional[dict[str, Any]] =
  None` field. Provider-specific entry-time forensic snapshot;
  schema-less by design — each provider populates its own keys.
  Not consumed by trading logic.
- `contracts/state_transition_event.v1.schema.json`: cross-repo single
  source of truth for the Signal Engine domain event format. Synced
  from `VantaBlack-Engine/contracts/`.
- `data/contract_specimens/state_transition_event_v1_specimens.jsonl`:
  6 known-scenario specimens for cross-repo contract validation.
- `tests/test_state_transition_event_contract.py`: validates each
  specimen against the frozen v1 schema (jsonschema dev dep).
- `scripts/sync_from_engine.py`: helper to re-sync schema + specimens
  when Engine bumps the v1 spec.
- `jsonschema>=4.0` dev dependency for the contract test.

### Documented (future use, not yet emitted)

- New Decision `reason_code` values that PM Stage 3 will emit:
  - `LAYER_1_SIGNAL_REVERSAL` — gated PM Layer 1 flip exit
    (`LAYER_1_SIGNAL_REVERSAL_EXIT_ENABLED` flag)
  - `LAYER_3_VOL_CRUSH_FAST` — 1min-cadence IV crush detection
    that pre-Stage-3 daily cadence would have missed

### Migration notes

- Backward-compat: pre-v0.1.6 Firestore docs without `signal_source` /
  without `entry_provider_context` deserialize cleanly (default kicks
  in for the former, None for the latter). Outer `extra="ignore"` is
  retained from v0.1.5.
- Stage 2 backfill script (`Core/scripts/backfill_intent_signal_source.py`)
  will normalize historical IntentBlocks where `signal_source IS NULL`
  → `"tv_legacy"`. After backfill completes, no Firestore docs will
  carry `null` for this field.
- No breaking changes vs v0.1.5 — version bump reflects additive
  multi-provider preparation.

## v0.1.5 — 2026-04-23

### Changed

- `IntentBlock.model_config.extra`: `"forbid"` → `"ignore"` on the outer
  model. Rationale: Core's `intent_store.save()` dual-writes both
  canonical keys (`intent_id`/`created_at`/`underlying`) AND legacy
  aliases (`id`/`timestamp`/`ticker`) to keep Core-internal Firestore
  queries at `src/services/intent_store.py:549,605,675-676,873-874`
  working during the 2026-05-10 alias-deprecation window. Validating
  read-side docs with the legacy extras present under `extra="forbid"`
  raised `extra_forbidden` errors, causing EXE + PM to reject every
  canonical-writer-produced doc. v0.1.5 tolerates the extras; inner
  sub-models (`GateResult`, `SanityCheckResult`, `IntentLegSpec`) keep
  `extra="forbid"` — typos in those shapes still fail loudly.

### Notes

- **Retirement trigger**: 2026-05-10 aliases-removal. At that point,
  Core's `intent_store.save()` drops the dual-write + Core-internal
  queries migrate to canonical field names. The outer `IntentBlock`
  flips back to `extra="forbid"`.
- **Discovered**: Phase D execution 2026-04-23. The contract bug was
  masked for 48h+ because all `_CanonicalIntentBlock.model_validate()`
  calls in Core raised on a separate sub-shape drift (7 errors in
  `l1_gate`/`l2_gate`/`sanity_check`) before the dual-write block
  executed. Hotfix to Core's `_core_block_to_canonical_dict` unblocked
  the validate step, revealing this latent second-layer bug.

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
