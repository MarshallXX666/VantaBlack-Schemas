"""IntentLegSpec — canonical leg shape.

Per Phase-B D3 = 3C (unified superset): combines EXE's 12-field
execution shape with PM's 5 market-snapshot fields (delta, iv, bid,
ask, oi). PM-side fields are Optional — writers set them when
available at enrichment time; execution-path code ignores them.

PM's legacy field `instrument` maps to canonical `option_type` via
a time-boxed alias; see `AliasChoices` on the `option_type` field.
TODO(aliases-remove-after-2026-05-10): drop `instrument` from
validation_alias once PM migrates readers.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from .enums import Currency, LegSide, MultiplierSource, OptionType


class IntentLegSpec(BaseModel):
    """Single leg of an options intent.

    Execution-side fields (required) come from EXE's Patch 11/16
    audit requirements — multiplier source + fetch time are needed
    to detect precheck rule 1 violations. Market-snapshot fields
    (Optional) come from PM's decision forensics.
    """

    # Execution (required for OrderBlock construction)
    leg_index: int
    side: LegSide
    opra_symbol: str
    tiger_symbol: str
    strike: float
    expiry: date
    option_type: OptionType = Field(
        validation_alias=AliasChoices("option_type", "instrument"),
    )
    ratio: int
    multiplier: int
    currency: Currency
    multiplier_source: MultiplierSource
    multiplier_fetched_at: datetime

    # Market snapshot (Optional, consumed by PM decision forensics)
    delta: Optional[float] = None
    iv: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    oi: Optional[int] = None

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
        use_enum_values=False,
    )
