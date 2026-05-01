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


def test_specimens_file_has_thirteen_entries(specimens: list[dict]) -> None:
    """Engine ships 13 specimens (v0.1.6 baseline 6 + v0.1.7 lifecycle/setup
    positive coverage 6 + 1 wire-omission specimen)."""
    assert len(specimens) == 13, (
        f"Expected 13 specimens, got {len(specimens)}. "
        "If the Engine added/removed specimens, update this test count and "
        "the labels list in test_v0_1_7_specimen_labels_present."
    )


def test_specimen_labels_present(specimens: list[dict]) -> None:
    """Every specimen must declare a label for forensic traceability."""
    labels = [s["specimen_label"] for s in specimens]
    assert all(isinstance(label, str) and label for label in labels), (
        f"Some specimens missing/empty labels: {labels}"
    )
    # Labels should be unique
    assert len(set(labels)) == len(labels), f"Duplicate labels: {labels}"


def test_v0_1_7_specimen_labels_present(specimens: list[dict]) -> None:
    """v0.1.7 added positive-coverage + wire-omission specimens. Each one
    locks a specific contract surface; missing any of them means a downstream
    consumer would have an unverified codepath for that scenario.
    """
    labels = {s["specimen_label"] for s in specimens}
    expected_v0_1_7 = {
        # positive coverage of new fields
        "breakout_birth_long",
        "pullback_resume_re_entry_short",
        "reversal_start_reversal_long",
        "pullback_resume_with_breakout_compositional",
        "persistent_momentum_shadow_long",
        "persistent_momentum_post_promotion_ongoing",
        # wire-omission (mirrors WebhookDispatcher's actual JSON output for
        # an event with default-valued v0.1.7 fields)
        "wire_default_omitted",
    }
    missing = expected_v0_1_7 - labels
    assert not missing, (
        f"v0.1.7 specimens missing: {missing}. The corpus must cover positive "
        "lifecycle/setup paths AND the wire-omission shape (default fields "
        "absent from JSON, not just defaulted)."
    )


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


def test_wire_omission_specimen_lacks_v0_1_7_fields(specimens: list[dict]) -> None:
    """The wire-omission specimen MUST NOT carry setup_composition or
    lifecycle_stage on the wire. WebhookDispatcher omits both when at default;
    if this specimen ever gains them, the corpus claim of "default-omitted
    payload validates" breaks."""
    wire = next((s for s in specimens if s["specimen_label"] == "wire_default_omitted"), None)
    assert wire is not None, "wire_default_omitted specimen missing"
    event = wire["event"]
    assert "setup_composition" not in event, (
        "wire_default_omitted MUST NOT carry setup_composition — that's the "
        "whole point of the omission test"
    )
    assert "lifecycle_stage" not in event, (
        "wire_default_omitted MUST NOT carry lifecycle_stage — that's the "
        "whole point of the omission test"
    )


def test_setup_tag_invariants_within_specimens(specimens: list[dict]) -> None:
    """Cross-field invariants the schema doesn't encode but consumers should
    rely on:
      - persistent_momentum tags during shadow phase MUST have live_status=False
        (until ongoing classifier promotes from shadow per §2.4)
      - tag direction matches event direction (sanity)
    Specimens are the contract for valid combinations; if Engine ever emits
    a violation, this test fails loud."""
    for s in specimens:
        label = s["specimen_label"]
        event = s["event"]
        composition = event.get("setup_composition", [])
        if not composition:
            continue
        for tag in composition:
            # Tag direction must match event direction
            assert tag["direction"] == event["direction"], (
                f"[{label}] tag {tag['name']} direction {tag['direction']} "
                f"!= event direction {event['direction']}"
            )
            # persistent_momentum tag during shadow → live_status MUST be False.
            # Exception: post-promotion specimen explicitly demonstrates the
            # post-shadow regime (live_status=True, lifecycle_stage="ongoing").
            if tag["name"] == "persistent_momentum":
                if label == "persistent_momentum_post_promotion_ongoing":
                    assert tag["live_status"] is True
                    assert event.get("lifecycle_stage") == "ongoing"
                else:
                    assert tag["live_status"] is False, (
                        f"[{label}] persistent_momentum tag MUST have "
                        "live_status=False during shadow phase per §2.4 rule #2"
                    )


def test_setup_tag_live_status_is_required_in_schema(schema: dict) -> None:
    """SetupTag.live_status must be REQUIRED in the schema. Defaulting to True
    silently coerces shadow components into live ones if a producer forgets
    to set it — that's the §2.4 isolation hole this requirement closes."""
    setup_tag_def = schema.get("$defs", {}).get("SetupTag", {})
    assert setup_tag_def, "SetupTag $def missing from schema"
    required = set(setup_tag_def.get("required", []))
    assert "live_status" in required, (
        "SetupTag.live_status MUST be required — defaulting to True is a "
        "shadow-isolation hole. See §2.4 rule #1."
    )
    assert {"name", "direction"}.issubset(required), (
        "SetupTag must require name + direction"
    )


def test_schema_is_self_consistent(schema: dict) -> None:
    """The schema document itself must conform to JSON Schema 2020-12."""
    # Already done in validator fixture, but assert here for explicit coverage.
    Draft202012Validator.check_schema(schema)
