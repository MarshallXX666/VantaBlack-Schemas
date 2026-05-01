"""Wire-compat contract: strict pre-v0.1.7 parsers REJECT every v0.1.7 event.

This test backs the CHANGELOG correction landed in PR #2: an earlier draft
claimed v0.1.7 was byte-compatible with strict v1 consumers via
omit-on-default for `setup_composition` / `lifecycle_stage`. That claim is
wrong. The current v0.1.7 wire shape always carries `event_id`, which was
NOT part of the v0.1.6 frozen schema. A strict consumer pinned to that
schema (`additionalProperties: false`) therefore rejects every v0.1.7
payload, regardless of which v0.1.7-specific fields are at default.

Practical implication: every consumer (Core / EXE / PM) MUST widen its
parser to accept `event_id` (and ideally `setup_composition` /
`lifecycle_stage` too) before it can ingest any v0.1.7 event.

The v0.1.6 schema is checked in as `tests/fixtures/state_transition_event_
v0_1_6.schema.json` — a snapshot, not a `git show main:` reference. Using
`main:` would self-destruct after this PR merges (main would point at the
v0.1.7 schema). The fixture is the immutable legacy contract; it's the
file consumers actually validated against before v0.1.7 shipped.

If a future change makes v0.1.7 events genuinely v1-strict-compatible
(e.g. `event_id` becomes optional or its absence on the wire is allowed),
this test will fail loud and force a deliberate CHANGELOG update — not a
silent regression of the documented wire-compat story.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECIMENS_PATH = (
    REPO_ROOT / "data" / "contract_specimens" / "state_transition_event_v1_specimens.jsonl"
)
LEGACY_SCHEMA_FIXTURE = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "state_transition_event_v0_1_6.schema.json"
)


def _load_legacy_schema() -> dict:
    """Load the v0.1.6 schema from the checked-in fixture.

    Snapshotted from `git show 43250bc:contracts/state_transition_event.v1.
    schema.json` (the v0.1.6 release commit). Do NOT replace this with a
    `main:` git ref — once this PR merges, `main` will hold the v0.1.7
    schema and the test's "legacy lacks event_id" precondition would
    silently flip.
    """
    with LEGACY_SCHEMA_FIXTURE.open() as f:
        return json.load(f)


def _load_specimens() -> list[dict]:
    specimens: list[dict] = []
    with SPECIMENS_PATH.open() as f:
        for line in f:
            line = line.strip()
            if line:
                specimens.append(json.loads(line))
    return specimens


@pytest.fixture(scope="module")
def legacy_schema() -> dict:
    return _load_legacy_schema()


@pytest.fixture(scope="module")
def legacy_validator(legacy_schema: dict) -> Draft202012Validator:
    Draft202012Validator.check_schema(legacy_schema)
    return Draft202012Validator(legacy_schema)


@pytest.fixture(scope="module")
def specimens() -> list[dict]:
    return _load_specimens()


class TestLegacySchemaPreconditions:
    """Sanity-check the assumptions this whole test file rests on."""

    def test_legacy_schema_uses_strict_additional_properties(
        self, legacy_schema: dict
    ) -> None:
        assert legacy_schema.get("additionalProperties") is False, (
            "v0.1.6 schema must be strict (additionalProperties=false) for the "
            "wire-compat-broken claim to hold; if main relaxed this, update "
            "CHANGELOG."
        )

    def test_legacy_schema_does_not_define_event_id(
        self, legacy_schema: dict
    ) -> None:
        assert "event_id" not in legacy_schema.get("properties", {}), (
            "v0.1.6 schema MUST NOT define event_id — that's the field whose "
            "newness in this PR breaks the byte-compat claim. If main now "
            "includes event_id, the CHANGELOG correction is stale."
        )

    def test_legacy_schema_does_not_define_v0_1_7_fields(
        self, legacy_schema: dict
    ) -> None:
        props = legacy_schema.get("properties", {})
        assert "setup_composition" not in props
        assert "lifecycle_stage" not in props


class TestEveryV017SpecimenRejectedByLegacyParser:
    """The load-bearing contract: legacy strict parser rejects all 13 specimens.

    Every v0.1.7 specimen carries `event_id`. The legacy schema has
    `additionalProperties: false` and does not list `event_id` as a known
    property. So validation must fail on every specimen with an error that
    cites `event_id` as the unrecognized property.
    """

    def test_all_specimens_fail_legacy_validation(
        self, specimens: list[dict], legacy_validator: Draft202012Validator
    ) -> None:
        passing: list[str] = []
        for s in specimens:
            label = s["specimen_label"]
            event = s["event"]
            errors = list(legacy_validator.iter_errors(event))
            if not errors:
                passing.append(label)
        assert not passing, (
            f"{len(passing)} specimen(s) unexpectedly passed legacy v0.1.6 "
            "schema validation. v0.1.7's CHANGELOG claims that's impossible "
            f"(every event carries new event_id). Passing: {passing}"
        )

    def test_event_id_is_the_culprit_for_every_specimen(
        self, specimens: list[dict], legacy_validator: Draft202012Validator
    ) -> None:
        """event_id must appear in the error trail for every specimen — that's
        what makes the wire-compat-broken story load-bearing (vs e.g. some
        specimens being broken for other reasons)."""
        for s in specimens:
            label = s["specimen_label"]
            event = s["event"]
            errors = list(legacy_validator.iter_errors(event))
            error_messages = " | ".join(e.message for e in errors)
            assert "event_id" in error_messages, (
                f"[{label}] expected event_id to be cited as an unrecognized "
                f"property under additionalProperties=false; instead got: "
                f"{error_messages}"
            )

    def test_wire_default_omitted_specimen_also_fails(
        self, specimens: list[dict], legacy_validator: Draft202012Validator
    ) -> None:
        """Spotlight test: the specimen that explicitly omits setup_composition
        and lifecycle_stage STILL fails legacy validation — because event_id
        cannot be omitted. This is the specific scenario the original
        byte-compat claim got wrong."""
        wire = next(
            (s for s in specimens if s["specimen_label"] == "wire_default_omitted"),
            None,
        )
        assert wire is not None, "wire_default_omitted specimen missing from corpus"
        event = wire["event"]
        # Sanity: the omission shape is what we think it is.
        assert "event_id" in event, (
            "wire_default_omitted MUST carry event_id — that's the field whose "
            "presence breaks legacy compat"
        )
        assert "setup_composition" not in event
        assert "lifecycle_stage" not in event
        errors = list(legacy_validator.iter_errors(event))
        assert errors, (
            "wire_default_omitted unexpectedly passes legacy validation; the "
            "byte-compat claim corrected in CHANGELOG would actually be true "
            "and this whole test file would be unjustified."
        )
        assert any("event_id" in e.message for e in errors), (
            "wire_default_omitted fails legacy validation, but not because of "
            f"event_id: {[e.message for e in errors]}"
        )
