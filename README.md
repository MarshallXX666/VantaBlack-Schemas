# vantablack-schemas

Shared Pydantic schemas for the VantaBlack trading system. This
package is the **single source of truth** for cross-repo data
contracts consumed by three repos:

- **Core** (`VantaBlack`) — signal generation; writes IntentBlock
  to Firestore `intents/` collection.
- **EXE** (`VantaBlack-EXE`) — execution; reads IntentBlock;
  produces OrderBlock, PositionBlock.
- **PM** (`VantaBlack-PM`) — position management, outcome
  tracking; reads IntentBlock + PositionBlock.

This package MUST NOT import from Core, EXE, or PM. It's a leaf
node in the dependency graph. Each consumer pins an explicit
version or git SHA.

## Contract discipline

Two hard rules:

1. **`extra="forbid"` on outer models.** No silent pass-through.
   New fields must be declared in the schema before any consumer
   can read them.
2. **`extra="allow"` is permitted ONLY on explicit extension points**
   — currently `EnrichmentData` and the raw `signal_data` dict.
   Anywhere else, `extra="allow"` in a PR is a code-review blocker.

## Versioning

- **v0.1.0** (2026-04-21): initial release. Includes **migration
  aliases** for three V2 field renames
  (`id`→`intent_id`, `timestamp`→`created_at`, `ticker`→`underlying`)
  and the `instrument`→`option_type` leg field rename. Aliases are
  **time-boxed** — see `CHANGELOG.md` for expiry dates.
- **v0.2.0** (planned, after rewrite-job — target 2026-05-10):
  remove aliases, require `signal_id`.

## Install (from git)

```bash
# Git-SHA pin (dev-friendly; pins to exact snapshot)
pip install git+ssh://git@github.com/MarshallXX666/VantaBlack-Schemas.git@<sha>

# Semver tag (release-friendly)
pip install git+ssh://git@github.com/MarshallXX666/VantaBlack-Schemas.git@v0.1.0
```

## Consumer usage

```python
from vantablack_schemas import IntentBlock, IntentStatus

# Deserialize a Firestore doc
intent = IntentBlock.model_validate(doc_dict)

# Attribute access uses canonical (new) names
print(intent.intent_id, intent.underlying, intent.created_at)

# Serialize — always emits canonical field names (no legacy)
new_doc = intent.model_dump(mode="json")
```

## Migration aliases

During the v0.1 window, readers accept both legacy and canonical
field names via Pydantic `AliasChoices`:

| Canonical (write + prefer) | Legacy alias (read-only) | Deadline |
|----------------------------|--------------------------|----------|
| `intent_id` | `id` | 2026-05-10 |
| `created_at` | `timestamp` | 2026-05-10 |
| `underlying` | `ticker` | 2026-05-10 |
| `option_type` (on IntentLegSpec) | `instrument` | 2026-05-10 |

After the rewrite-job backfills old Firestore docs into the
canonical shape, v0.2.0 drops the aliases.

## Development

```bash
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e '.[dev]'
pytest
```
