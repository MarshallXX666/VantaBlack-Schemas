"""Canonical enums shared across Core / EXE / PM.

Values are taken from EXE's `execution/schemas.py` as the authoritative
source (stronger typing than Core's Literal-of-strings). See
Phase-B decision D1 = 1A (adopt EXE-style names/types).
"""
from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# Intent lifecycle — V3 canonical + V2 legacy compat
# ---------------------------------------------------------------------------
class IntentStatus(str, Enum):
    """Execution-lifecycle status.

    V3 values are the canonical set used by all new code. V2 legacy
    values are retained ONLY to deserialize historical Firestore docs
    written before the Track 2A rename. New writers MUST NOT emit
    them.

    TODO(aliases-remove-after-2026-05-10): drop V2 legacy members in
    v0.2.0 after the rewrite-job backfills old docs.
    """

    # V3 canonical (write + read)
    PENDING_EXECUTION = "PENDING_EXECUTION"
    CLAIMED = "CLAIMED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"

    # V2 legacy (read-only, DO NOT WRITE)
    REJECTED = "REJECTED"
    PLANNED = "PLANNED"
    ENTERED = "ENTERED"
    ACTIVE = "ACTIVE"
    EXITED = "EXITED"


class IntentState(str, Enum):
    """V3 position-lifecycle state machine (Core authoritative).

    Transitions:
        PROPOSED → ACTIVE | SKIPPED | EXPIRED
        ACTIVE   → CLOSED_WIN | CLOSED_LOSS
    """

    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    CLOSED_WIN = "CLOSED_WIN"
    CLOSED_LOSS = "CLOSED_LOSS"
    EXPIRED = "EXPIRED"
    SKIPPED = "SKIPPED"


class IntentType(str, Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"


# ---------------------------------------------------------------------------
# Mode + direction
# ---------------------------------------------------------------------------
class ExecutionMode(str, Enum):
    AUTO = "AUTO"
    MANUAL_TELEGRAM = "MANUAL_TELEGRAM"


class IntentDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


# ---------------------------------------------------------------------------
# Structure + time-in-force
# ---------------------------------------------------------------------------
class StructureType(str, Enum):
    """Position structure.

    V3 canonical members are direction-specific (NAKED_LONG_CALL vs
    NAKED_LONG_PUT). The legacy V2 member NAKED_LONG is retained ONLY
    for pre-V3 Firestore docs where direction was inferred separately.

    TODO(aliases-remove-after-2026-05-10): drop V2 legacy NAKED_LONG in
    v0.2.0 after rewrite-job backfills old docs.
    """

    # V3 canonical (EXE Patch 7)
    NAKED_LONG_CALL = "NAKED_LONG_CALL"
    NAKED_LONG_PUT = "NAKED_LONG_PUT"
    # MANUAL_TELEGRAM
    VERTICAL_DEBIT_CALL = "VERTICAL_DEBIT_CALL"
    VERTICAL_DEBIT_PUT = "VERTICAL_DEBIT_PUT"
    # V2 legacy (read-only)
    NAKED_LONG = "NAKED_LONG"


class TimeInForce(str, Enum):
    DAY = "DAY"
    GTC = "GTC"


# ---------------------------------------------------------------------------
# Market snapshot taxonomy
# ---------------------------------------------------------------------------
class IVRegime(str, Enum):
    """IV-regime classifier output.

    V3 canonical values are COLD/COOL/WARM/HOT. The legacy V2 value
    NORMAL is retained ONLY for backward compat with pre-V3 Firestore
    docs — new writers MUST NOT emit it.

    TODO(aliases-remove-after-2026-05-10): drop V2 legacy NORMAL in
    v0.2.0 after rewrite-job backfills old docs.
    """

    # V3 canonical
    COLD = "COLD"
    COOL = "COOL"
    WARM = "WARM"
    HOT = "HOT"
    # V2 legacy (read-only)
    NORMAL = "NORMAL"


class NarrativeType(str, Enum):
    TECHNICAL_BREAKOUT = "TECHNICAL_BREAKOUT"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    PARADIGM_SHIFT = "PARADIGM_SHIFT"
    TECHNICAL_SQUEEZE = "TECHNICAL_SQUEEZE"


class SanityAction(str, Enum):
    NORMAL = "NORMAL"
    DOWNGRADE = "DOWNGRADE"
    UPGRADE = "UPGRADE"


# ---------------------------------------------------------------------------
# Leg-level
# ---------------------------------------------------------------------------
class LegSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class Currency(str, Enum):
    USD = "USD"
    HKD = "HKD"
    CNY = "CNY"


class MultiplierSource(str, Enum):
    ORATS = "ORATS"
    TIGER_CONTRACT_MASTER = "TIGER_CONTRACT_MASTER"
    HARDCODED = "HARDCODED"
