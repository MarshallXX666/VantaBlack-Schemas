# vantablack-schemas — deprecation + backlog tracker

**Purpose**: time-boxed deprecations + cross-version intentions.
Entries here are the authoritative source for "when do we remove
this legacy thing?" questions. Matches the discipline from
`VantaBlack-EXE/feedback_contract_discipline.md` Rule 3
(every deprecation must have an explicit expiration date + tracking
entry + DeprecationWarning).

---

## Scheduled for removal in v0.2.0 (target release 2026-05-15)

The v0.2.0 release is the canonical "A+B transition artifacts gone"
release. It drops everything that existed only to bridge the
Track 2A schema-rename and Track 2E retry-semantic migrations.

### Field-rename migration aliases (from v0.1.0)

`IntentBlock.intent_id` — drop the `AliasChoices("intent_id", "id")`
alias; canonical name only.
`IntentBlock.created_at` — drop the `AliasChoices("created_at", "timestamp")`
alias; canonical name only.
`IntentBlock.underlying` — drop the `AliasChoices("underlying", "ticker")`
alias; canonical name only.
`IntentLegSpec.option_type` — drop the `AliasChoices("option_type", "instrument")`
alias; canonical name only.

Gate on rewrite-job completion (see 2A Phase D). The rewrite-job
backfills all historical Firestore docs into canonical shape
before v0.2.0 ships.

### V2 legacy enum members (from v0.1.0 / v0.1.3)

`IntentStatus.REJECTED / PLANNED / ENTERED / ACTIVE / EXITED` —
V2 lifecycle values retained for backward reads only. Drop once
rewrite-job cleans historical docs.
`IVRegime.NORMAL` — V2 classifier value. Drop with rewrite-job.
`StructureType.NAKED_LONG` — V2 direction-inferred. Drop with
rewrite-job.

### Retry-semantic legacy (from v0.1.4 / Track 2E Phase B)

`SizeRejectReason.SIZE_REJECTED_STALE_MARK` (EXE-owned enum, not in
Schemas today but tracked here because the semantic change is
cross-repo) — pre-A+B terminal reason code. After Track 2E Phase B
ships, this code is NEVER written; historical `SKIPPED` intents
carrying this reason remain readable. Drop in EXE v0.2.0-aligned
release; tracked here for coordination with Schemas v0.2.0's
alias-drop wave.

Expiration deadline: **2026-05-15** (tied to v0.2.0).

DeprecationWarning policy: every reference to a scheduled-for-removal
member must emit `DeprecationWarning` at access time. Python 3.12+
supports `warnings.deprecated` decorator directly on enum members;
use it rather than manual `__getattr__` overrides.

---

## Non-time-boxed tech debt (separate from deprecation window)

_(none yet — place open items here that aren't tied to v0.2.0)_

---

## How to use

- **Before merging a deprecation**: add an entry here with
  (item, target-version, deadline). Reviewer blocks PR if missing.
- **At release time**: whichever entries have a target-version
  matching the release must be removed before the tag lands.
- **Past deadline without removal**: contract-discipline Rule 3
  is violated — the PR that lets this happen is a Day 1-class
  drift incident, not a "we'll get to it". Treat accordingly.
