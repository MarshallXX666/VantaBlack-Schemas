from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from vantablack_schemas import (
    StrategyEngineWireIntegrityError,
    StrategyEngineWireSchemaError,
    StrategyEngineWireSemanticError,
    canonical_strategy_engine_payload_hash,
    validate_strategy_engine_wire_message,
    verify_strategy_engine_wire_integrity,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts/strategy_engine_wire_message.v1.schema.json"
SPECIMEN_PATH = ROOT / "data/contract_specimens/strategy_engine_wire_message_v1_specimens.jsonl"
PRODUCER_SCHEMA_SHA256 = "1da447a33b35bd5d7a6c538aef10b2ca1c592efc5a2bfd053288d8b7d478d651"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def specimens() -> list[dict]:
    return [
        json.loads(line)
        for line in SPECIMEN_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _specimen(specimens: list[dict], contract_name: str) -> dict:
    return next(copy.deepcopy(item) for item in specimens if item["contract_name"] == contract_name)


def _resign(message: dict) -> None:
    payload_hash = canonical_strategy_engine_payload_hash(message["payload"])
    normalized = "".join(
        f"_{character.lower()}" if character.isupper() else character
        for character in message["contract_name"]
    ).lstrip("_")
    message["payload_hash"] = payload_hash
    message["message_id"] = f"wire_{normalized}_{payload_hash[:24]}"


def test_schema_matches_strategy_engine_producer_fingerprint(schema: dict) -> None:
    digest = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
    assert digest == PRODUCER_SCHEMA_SHA256
    Draft202012Validator.check_schema(schema)


def test_all_four_wire_contract_specimens_validate(schema: dict, specimens: list[dict]) -> None:
    validator = Draft202012Validator(schema)
    for specimen in specimens:
        validator.validate(specimen)
        validate_strategy_engine_wire_message(specimen)
    assert {specimen["contract_name"] for specimen in specimens} == {
        "StrategyProposal",
        "PortfolioAccountSnapshot",
        "CapitalReservation",
        "PortfolioDecision",
    }


def test_contract_name_and_version_are_required(schema: dict, specimens: list[dict]) -> None:
    validator = Draft202012Validator(schema)
    for field in ("contract_name", "contract_version"):
        invalid = copy.deepcopy(specimens[0])
        invalid.pop(field)
        assert list(validator.iter_errors(invalid)), field


def test_shadow_decision_cannot_claim_execution_authority(
    schema: dict, specimens: list[dict]
) -> None:
    decision = next(
        copy.deepcopy(item) for item in specimens if item["contract_name"] == "PortfolioDecision"
    )
    decision["payload"]["executable"] = True
    assert list(Draft202012Validator(schema).iter_errors(decision))


def test_account_strategy_exposure_cannot_be_negative(schema: dict, specimens: list[dict]) -> None:
    account = next(
        copy.deepcopy(item)
        for item in specimens
        if item["contract_name"] == "PortfolioAccountSnapshot"
    )
    account["payload"]["per_strategy_exposure_s10k"]["TEST_STRATEGY"] = -1
    assert list(Draft202012Validator(schema).iter_errors(account))


def test_unknown_outer_fields_fail_closed(schema: dict, specimens: list[dict]) -> None:
    invalid = copy.deepcopy(specimens[0])
    invalid["unexpected"] = "forbidden"
    assert list(Draft202012Validator(schema).iter_errors(invalid))


def test_payload_mutation_fails_integrity_check(specimens: list[dict]) -> None:
    invalid = copy.deepcopy(specimens[0])
    invalid["payload"]["requested_risk_s10k"] += 1
    with pytest.raises(StrategyEngineWireIntegrityError, match="payload_hash mismatch"):
        verify_strategy_engine_wire_integrity(invalid)


def test_runtime_validator_rejects_structurally_incomplete_signed_message(
    specimens: list[dict],
) -> None:
    invalid = copy.deepcopy(specimens[0])
    invalid["payload"].pop("instrument")
    payload_hash = hashlib.sha256(
        json.dumps(invalid["payload"], sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    invalid["payload_hash"] = payload_hash
    invalid["message_id"] = f"wire_strategy_proposal_{payload_hash[:24]}"
    with pytest.raises(StrategyEngineWireSchemaError, match="schema violation"):
        validate_strategy_engine_wire_message(invalid)


def test_runtime_validator_enforces_date_time_format(specimens: list[dict]) -> None:
    invalid = _specimen(specimens, "StrategyProposal")
    invalid["payload"]["valid_from"] = "not-a-date-time"
    _resign(invalid)
    with pytest.raises(StrategyEngineWireSchemaError, match="schema violation"):
        validate_strategy_engine_wire_message(invalid)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("expires_at", "2026-07-22T20:05:00Z", "expires_at"),
        ("dry_run", False, "must be dry_run"),
        ("requested_risk_s10k", 0, "positive requested risk"),
    ],
)
def test_runtime_validator_enforces_proposal_semantics(
    specimens: list[dict], field: str, value: object, match: str
) -> None:
    invalid = _specimen(specimens, "StrategyProposal")
    invalid["payload"][field] = value
    _resign(invalid)
    with pytest.raises(StrategyEngineWireSemanticError, match=match):
        validate_strategy_engine_wire_message(invalid)


def test_runtime_validator_rejects_data_cutoff_time_travel(specimens: list[dict]) -> None:
    invalid = _specimen(specimens, "StrategyProposal")
    invalid["payload"]["data_cutoff"]["observed_at"] = "2026-07-22T20:04:00Z"
    _resign(invalid)
    with pytest.raises(StrategyEngineWireSemanticError, match="cannot precede"):
        validate_strategy_engine_wire_message(invalid)


@pytest.mark.parametrize(
    ("updates", "match"),
    [
        ({"reserved_risk_s10k": 30_000_001}, "cannot exceed"),
        ({"status": "rejected"}, "cannot reserve"),
        ({"account_version_after": 7}, "advance account version"),
    ],
)
def test_runtime_validator_enforces_reservation_semantics(
    specimens: list[dict], updates: dict, match: str
) -> None:
    invalid = _specimen(specimens, "CapitalReservation")
    invalid["payload"].update(updates)
    _resign(invalid)
    with pytest.raises(StrategyEngineWireSemanticError, match=match):
        validate_strategy_engine_wire_message(invalid)


@pytest.mark.parametrize(
    ("updates", "match"),
    [
        ({"reservation_id": None}, "requires reservation_id"),
        ({"outcome": "rejected"}, "cannot approve capital"),
    ],
)
def test_runtime_validator_enforces_decision_semantics(
    specimens: list[dict], updates: dict, match: str
) -> None:
    invalid = _specimen(specimens, "PortfolioDecision")
    invalid["payload"].update(updates)
    _resign(invalid)
    with pytest.raises(StrategyEngineWireSemanticError, match=match):
        validate_strategy_engine_wire_message(invalid)
