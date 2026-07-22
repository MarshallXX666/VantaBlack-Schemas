from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


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


def canonical_strategy_engine_payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def verify_strategy_engine_wire_integrity(message: Mapping[str, Any]) -> None:
    contract_name = message.get("contract_name")
    if contract_name not in STRATEGY_ENGINE_CONTRACT_NAMES:
        raise StrategyEngineWireIntegrityError("unknown strategy-engine contract_name")
    if message.get("contract_version") != STRATEGY_ENGINE_WIRE_VERSION:
        raise StrategyEngineWireIntegrityError(
            "unsupported strategy-engine contract_version"
        )
    payload = message.get("payload")
    if not isinstance(payload, Mapping):
        raise StrategyEngineWireIntegrityError(
            "strategy-engine payload must be an object"
        )
    payload_hash = canonical_strategy_engine_payload_hash(payload)
    if message.get("payload_hash") != payload_hash:
        raise StrategyEngineWireIntegrityError("strategy-engine payload_hash mismatch")
    expected_id = _wire_message_id(contract_name, payload_hash)
    if message.get("message_id") != expected_id:
        raise StrategyEngineWireIntegrityError("strategy-engine message_id mismatch")


def _wire_message_id(contract_name: str, payload_hash: str) -> str:
    normalized = "".join(
        f"_{character.lower()}" if character.isupper() else character
        for character in contract_name
    ).lstrip("_")
    return f"wire_{normalized}_{payload_hash[:24]}"


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
    return Draft202012Validator(schema)
