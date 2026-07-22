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
    validate_strategy_engine_wire_message,
    verify_strategy_engine_wire_integrity,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "contracts/strategy_engine_wire_message.v1.schema.json"
SPECIMEN_PATH = (
    ROOT / "data/contract_specimens/strategy_engine_wire_message_v1_specimens.jsonl"
)
PRODUCER_SCHEMA_SHA256 = (
    "f6c77b56919bed08228715c26cbdc9ae418be7cc7d86862339a35aa2dd512ea3"
)


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


def test_schema_matches_strategy_engine_producer_fingerprint(schema: dict) -> None:
    digest = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
    assert digest == PRODUCER_SCHEMA_SHA256
    Draft202012Validator.check_schema(schema)


def test_all_four_wire_contract_specimens_validate(
    schema: dict, specimens: list[dict]
) -> None:
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


def test_contract_name_and_version_are_required(
    schema: dict, specimens: list[dict]
) -> None:
    validator = Draft202012Validator(schema)
    for field in ("contract_name", "contract_version"):
        invalid = copy.deepcopy(specimens[0])
        invalid.pop(field)
        assert list(validator.iter_errors(invalid)), field


def test_shadow_decision_cannot_claim_execution_authority(
    schema: dict, specimens: list[dict]
) -> None:
    decision = next(
        copy.deepcopy(item)
        for item in specimens
        if item["contract_name"] == "PortfolioDecision"
    )
    decision["payload"]["executable"] = True
    assert list(Draft202012Validator(schema).iter_errors(decision))


def test_account_strategy_exposure_cannot_be_negative(
    schema: dict, specimens: list[dict]
) -> None:
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
        json.dumps(invalid["payload"], sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    invalid["payload_hash"] = payload_hash
    invalid["message_id"] = f"wire_strategy_proposal_{payload_hash[:24]}"
    with pytest.raises(StrategyEngineWireSchemaError, match="schema violation"):
        validate_strategy_engine_wire_message(invalid)
