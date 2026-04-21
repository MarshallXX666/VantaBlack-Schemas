"""Shared golden fixtures for cross-repo contract tests.

Consumers (EXE, PM, Core CI) import these via:

    from vantablack_schemas.fixtures import (
        LEGACY_CORE_PAYLOAD,
        CANONICAL_CORE_PAYLOAD,
        EDGE_CASE_PAYLOADS,
    )

The fixtures mirror what Core writes to Firestore `intents/`.
They are kept in-package (not in tests/) so downstream consumer
repos can import them without needing the Schemas tests tree.
"""
from __future__ import annotations

from ._payloads import (
    CANONICAL_CORE_PAYLOAD,
    EDGE_CASE_PAYLOADS,
    LEGACY_CORE_PAYLOAD,
    canonical_core_payload,
    legacy_core_payload,
)

__all__ = [
    "LEGACY_CORE_PAYLOAD",
    "CANONICAL_CORE_PAYLOAD",
    "EDGE_CASE_PAYLOADS",
    "legacy_core_payload",
    "canonical_core_payload",
]
