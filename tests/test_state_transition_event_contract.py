"""Contract test: 6 StateTransitionEvent specimens parse against frozen schema.

The JSON Schema at `contracts/state_transition_event.v1.schema.json` is the
cross-repo single source of truth for the Signal Engine event format. Each
specimen in `data/contract_specimens/state_transition_event_v1_specimens.jsonl`
represents a known scenario that consumers (Core /api/signal/webhook) must
parse without error.

If this test fails after a sync from Engine, EITHER:
- the schema changed (intentional → bump major version + coordinate consumer
  migration), OR
- a specimen has a typo / outdated payload → re-sync from Engine.

Per `feedback_contract_discipline.md`: schema-as-source-of-truth, no shared
pydantic across repos. Each consumer (Core / EXE / PM) implements its own
pydantic model from this schema.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "contracts" / "state_transition_event.v1.schema.json"
SPECIMENS_PATH = (
    REPO_ROOT / "data" / "contract_specimens" / "state_transition_event_v1_specimens.jsonl"
)


def _load_schema() -> dict:
    with SCHEMA_PATH.open() as f:
        return json.load(f)


def _load_specimens() -> list[dict]:
    """Load specimens jsonl. Each line: {'specimen_label': str, 'event': {...}}."""
    specimens: list[dict] = []
    with SPECIMENS_PATH.open() as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                specimens.append(json.loads(line))
            except json.JSONDecodeError as exc:
                pytest.fail(
                    f"Specimen line {line_num} is not valid JSON: {exc}"
                )
    return specimens


@pytest.fixture(scope="module")
def schema() -> dict:
    return _load_schema()


@pytest.fixture(scope="module")
def validator(schema: dict) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture(scope="module")
def specimens() -> list[dict]:
    return _load_specimens()


def test_specimens_file_has_six_entries(specimens: list[dict]) -> None:
    """Engine ships 6 specimens covering known scenarios."""
    assert len(specimens) == 6, (
        f"Expected 6 specimens, got {len(specimens)}. "
        "If the Engine added/removed specimens, update this test count and "
        "the labels list in test_specimen_labels_present."
    )


def test_specimen_labels_present(specimens: list[dict]) -> None:
    """Every specimen must declare a label for forensic traceability."""
    labels = [s["specimen_label"] for s in specimens]
    assert all(isinstance(label, str) and label for label in labels), (
        f"Some specimens missing/empty labels: {labels}"
    )
    # Labels should be unique
    assert len(set(labels)) == len(labels), f"Duplicate labels: {labels}"


def test_all_specimens_validate_against_schema(
    specimens: list[dict], validator: Draft202012Validator
) -> None:
    """Each specimen's `event` payload must validate against the v1 schema.

    This is the cross-repo contract: if any specimen fails here, downstream
    consumers (Core /api/signal/webhook pydantic parser) will reject those
    events at runtime.
    """
    failures: list[str] = []
    for s in specimens:
        label = s.get("specimen_label", "<unlabeled>")
        event = s.get("event")
        if event is None:
            failures.append(f"[{label}] missing 'event' field")
            continue
        errors = sorted(validator.iter_errors(event), key=lambda e: e.path)
        if errors:
            for err in errors:
                failures.append(
                    f"[{label}] {'.'.join(str(p) for p in err.path) or '<root>'}: "
                    f"{err.message}"
                )
    if failures:
        pytest.fail(
            f"{len(failures)} schema validation failure(s):\n  - "
            + "\n  - ".join(failures)
        )


def test_schema_is_self_consistent(schema: dict) -> None:
    """The schema document itself must conform to JSON Schema 2020-12."""
    # Already done in validator fixture, but assert here for explicit coverage.
    Draft202012Validator.check_schema(schema)
