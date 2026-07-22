from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

STRATEGY_ENGINE_WIRE_VERSION = "1.0.0"
STRATEGY_ENGINE_CONTRACT_NAMES = frozenset(
    {
        "StrategyProposal",
        "PortfolioAccountSnapshot",
        "CapitalReservation",
        "PortfolioDecision",
    }
)


class StrategyEngineWireIntegrityError(ValueError):
    pass


class StrategyEngineWireSchemaError(ValueError):
    pass


class StrategyEngineWireSemanticError(ValueError):
    pass


def validate_strategy_engine_wire_message(message: Mapping[str, Any]) -> None:
    """Validate the complete v1 schema and then its content-derived identity."""

    errors = sorted(
        _wire_validator().iter_errors(message),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    if errors:
        error = errors[0]
        path = "$" + "".join(f"[{item!r}]" for item in error.absolute_path)
        raise StrategyEngineWireSchemaError(
            f"strategy-engine wire schema violation at {path}: {error.message}"
        )
    verify_strategy_engine_wire_integrity(message)
    validate_strategy_engine_wire_semantics(message)


def validate_strategy_engine_wire_semantics(message: Mapping[str, Any]) -> None:
    """Apply producer-side invariants that JSON Schema cannot express."""

    contract_name = message["contract_name"]
    payload = message["payload"]
    if contract_name == "StrategyProposal":
        _validate_proposal(payload)
    elif contract_name == "CapitalReservation":
        _validate_reservation(payload)
    elif contract_name == "PortfolioDecision":
        _validate_decision(payload)


def canonical_strategy_engine_payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_strategy_engine_wire_integrity(message: Mapping[str, Any]) -> None:
    contract_name = message.get("contract_name")
    if contract_name not in STRATEGY_ENGINE_CONTRACT_NAMES:
        raise StrategyEngineWireIntegrityError("unknown strategy-engine contract_name")
    if message.get("contract_version") != STRATEGY_ENGINE_WIRE_VERSION:
        raise StrategyEngineWireIntegrityError("unsupported strategy-engine contract_version")
    payload = message.get("payload")
    if not isinstance(payload, Mapping):
        raise StrategyEngineWireIntegrityError("strategy-engine payload must be an object")
    try:
        payload_hash = canonical_strategy_engine_payload_hash(payload)
    except (TypeError, ValueError) as exc:
        raise StrategyEngineWireIntegrityError(
            "strategy-engine payload is not strict canonical JSON"
        ) from exc
    if message.get("payload_hash") != payload_hash:
        raise StrategyEngineWireIntegrityError("strategy-engine payload_hash mismatch")
    expected_id = _wire_message_id(contract_name, payload_hash)
    if message.get("message_id") != expected_id:
        raise StrategyEngineWireIntegrityError("strategy-engine message_id mismatch")


def _wire_message_id(contract_name: str, payload_hash: str) -> str:
    normalized = "".join(
        f"_{character.lower()}" if character.isupper() else character for character in contract_name
    ).lstrip("_")
    return f"wire_{normalized}_{payload_hash[:24]}"


def _timestamp(payload: Mapping[str, Any], field: str) -> datetime:
    value = payload[field]
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_aware_date_time(value: object) -> bool:
    if not isinstance(value, str):
        return True
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


_STRATEGY_ENGINE_FORMAT_CHECKER = FormatChecker()
_STRATEGY_ENGINE_FORMAT_CHECKER.checkers["date-time"] = (
    _is_aware_date_time,
    (ValueError,),
)


def _semantic_error(message: str) -> None:
    raise StrategyEngineWireSemanticError(message)


def _validate_proposal(payload: Mapping[str, Any]) -> None:
    signal_as_of = _timestamp(payload, "signal_as_of")
    valid_from = _timestamp(payload, "valid_from")
    expires_at = _timestamp(payload, "expires_at")
    cutoff = payload["data_cutoff"]
    cutoff_as_of = _timestamp(cutoff, "as_of")
    observed_at = _timestamp(cutoff, "observed_at")
    vendors = cutoff["vendors"]
    dataset_hashes = cutoff["dataset_hashes"]
    if expires_at <= valid_from:
        _semantic_error("proposal expires_at must be after valid_from")
    if signal_as_of > valid_from:
        _semantic_error("proposal signal_as_of cannot be after valid_from")
    if cutoff_as_of > signal_as_of:
        _semantic_error("data cutoff as_of cannot be after signal_as_of")
    if observed_at < cutoff_as_of:
        _semantic_error("data cutoff observed_at cannot precede as_of")
    if observed_at > valid_from:
        _semantic_error("data cutoff cannot be observed after valid_from")
    if not vendors or any(not vendor.strip() for vendor in vendors):
        _semantic_error("data cutoff vendors must be non-empty")
    if len(vendors) != len(set(vendors)):
        _semantic_error("data cutoff vendors must be unique")
    if not dataset_hashes or any(not name.strip() for name in dataset_hashes):
        _semantic_error("data cutoff requires named dataset hashes")
    if any(
        len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest)
        for digest in dataset_hashes.values()
    ):
        _semantic_error("dataset hashes must be lowercase SHA-256 digests")
    mode = payload["mode"]
    dry_run = payload["dry_run"]
    if mode == "live" and dry_run:
        _semantic_error("live proposal cannot be dry_run")
    if mode != "live" and not dry_run:
        _semantic_error("non-live proposal must be dry_run")
    action = payload["action"]
    if action in {"open", "increase"}:
        if payload["requested_risk_s10k"] <= 0:
            _semantic_error("capital-consuming proposal requires positive requested risk")
        if payload.get("target_weight") in {None, 0}:
            _semantic_error("capital-consuming proposal requires non-zero target_weight")
    if action == "close" and payload.get("target_weight") != 0:
        _semantic_error("close proposal requires target_weight=0")


def _validate_reservation(payload: Mapping[str, Any]) -> None:
    requested = payload["requested_risk_s10k"]
    reserved = payload["reserved_risk_s10k"]
    version_before = payload["account_version_before"]
    version_after = payload["account_version_after"]
    if reserved > requested:
        _semantic_error("reserved risk cannot exceed requested risk")
    if payload["status"] == "rejected":
        if reserved != 0:
            _semantic_error("rejected reservation cannot reserve capital")
        if version_after != version_before:
            _semantic_error("rejected reservation cannot advance account version")
    else:
        if reserved <= 0:
            _semantic_error("capital reservation must preserve positive reserved risk")
        if version_after != version_before + 1:
            _semantic_error("capital reservation must advance account version once")


def _validate_decision(payload: Mapping[str, Any]) -> None:
    outcome = payload["outcome"]
    approved_risk = payload["approved_risk_s10k"]
    if outcome == "approved" and approved_risk > 0 and not payload.get("reservation_id"):
        _semantic_error("capital approval requires reservation_id")
    if outcome != "approved" and approved_risk != 0:
        _semantic_error("non-approved decision cannot approve capital")


@lru_cache(maxsize=1)
def _wire_validator() -> Draft202012Validator:
    resource = resources.files("vantablack_schemas").joinpath(
        "contracts/strategy_engine_wire_message.v1.schema.json"
    )
    if resource.is_file():
        schema = json.loads(resource.read_text(encoding="utf-8"))
    else:
        source_schema = (
            Path(__file__).resolve().parents[2]
            / "contracts/strategy_engine_wire_message.v1.schema.json"
        )
        schema = json.loads(source_schema.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(
        schema,
        format_checker=_STRATEGY_ENGINE_FORMAT_CHECKER,
    )
