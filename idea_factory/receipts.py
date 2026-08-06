"""Parse + validate agent JSON receipts against the typed schema.

Agents return their final message containing an `idea_factory_receipt_v1` JSON
block (possibly surrounded by prose, fenced, or both). This module:

- extracts the JSON block from a raw agent message
- validates it against the right Pydantic receipt type for its `stage`
- returns either the typed receipt or a `ReceiptError` describing what failed

The PM uses `parse()` to validate every dispatch return before routing; never
trusts prose to make routing decisions.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional, Union

from idea_factory.schema import (
    AnalystReceipt,
    BuilderReceipt,
    ClustererReceipt,
    IngestorReceipt,
    MarketScoutReceipt,
    ScorerReceipt,
    ValidatorReceipt,
)

RECEIPT_BY_STAGE = {
    "00": MarketScoutReceipt,
    "01": IngestorReceipt,
    "02": AnalystReceipt,
    "04": ScorerReceipt,
    "05": ValidatorReceipt,
    "06": BuilderReceipt,
    "07": ClustererReceipt,
}

# Accept both ```json fenced and bare JSON. Be liberal with whitespace.
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_BARE_RE = re.compile(r'(\{\s*"idea_factory_receipt_v1".*?\})\s*$', re.DOTALL)


@dataclass(frozen=True)
class ReceiptError:
    stage: Optional[str]
    reason: str
    raw: str


def _extract_json(raw: str) -> Optional[dict]:
    m = _FENCE_RE.search(raw)
    if m:
        return json.loads(m.group(1))
    m = _BARE_RE.search(raw)
    if m:
        return json.loads(m.group(1))
    # last-resort: try the whole thing
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return None


def parse(raw: str) -> Union[
    IngestorReceipt, AnalystReceipt, ScorerReceipt,
    ValidatorReceipt, BuilderReceipt, ClustererReceipt, ReceiptError,
]:
    """Extract + validate. Returns the typed receipt, or a ReceiptError."""
    if not raw or not raw.strip():
        return ReceiptError(stage=None, reason="empty input", raw=raw)

    try:
        payload = _extract_json(raw)
    except json.JSONDecodeError as e:
        return ReceiptError(stage=None, reason=f"invalid JSON: {e.msg}", raw=raw)

    if payload is None:
        return ReceiptError(stage=None, reason="no idea_factory_receipt_v1 block found", raw=raw)

    if "schema_version" not in payload or payload["schema_version"] != "idea_factory_receipt_v1":
        return ReceiptError(
            stage=payload.get("stage"),
            reason='missing or wrong schema_version; expected "idea_factory_receipt_v1"',
            raw=raw,
        )

    stage = payload.get("stage")
    if stage not in RECEIPT_BY_STAGE:
        return ReceiptError(
            stage=stage,
            reason=f"unknown stage {stage!r}; expected one of {sorted(RECEIPT_BY_STAGE)}",
            raw=raw,
        )

    cls = RECEIPT_BY_STAGE[stage]
    try:
        return cls.model_validate(payload)
    except Exception as e:  # pydantic ValidationError carries rich details
        return ReceiptError(stage=stage, reason=str(e), raw=raw)