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
    InfraScorerReceipt,
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

# Stage 04 is shared by the per-startup scorer and the infra-node scorer.
# Disambiguate on a field that only the infra scorer emits.
_INFRA_SCORER_DISCRIMINATOR = "infra_nodes_scored"

# Accept ```json fenced blocks. Capture the *fence body* only — nested JSON
# objects must be parsed with a balanced-brace scan (a non-greedy `\{.*?\}`
# regex truncates at the first `}` and breaks MarketScout/Clusterer receipts).
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

_RECEIPT_MARKER = "idea_factory_receipt_v1"


@dataclass(frozen=True)
class ReceiptError:
    stage: Optional[str]
    reason: str
    raw: str


def _balanced_receipt_scan(text: str) -> Optional[dict]:
    """Walk every '{' and keep the LAST full JSON object with the receipt marker.

    Agents commonly emit a trailing receipt after prose, and sometimes an
    unrelated JSON snippet earlier in the message. Nested objects are fine —
    raw_decode consumes the whole balanced object.
    """
    decoder = json.JSONDecoder()
    last_payload: Optional[dict] = None
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("schema_version") == _RECEIPT_MARKER:
            last_payload = obj
    return last_payload


def _extract_json(raw: str) -> Optional[dict]:
    # 1. fenced block(s): prefer the last fence that yields a valid receipt
    fence_payload: Optional[dict] = None
    for m in _FENCE_RE.finditer(raw):
        body = m.group(1)
        try:
            obj = json.loads(body)
            if isinstance(obj, dict) and obj.get("schema_version") == _RECEIPT_MARKER:
                fence_payload = obj
                continue
        except json.JSONDecodeError:
            pass
        # fence body may have prose + JSON; fall back to balanced scan inside it
        scanned = _balanced_receipt_scan(body)
        if scanned is not None:
            fence_payload = scanned
    if fence_payload is not None:
        return fence_payload

    # 2. balanced-brace scan over the whole message
    scanned = _balanced_receipt_scan(raw)
    if scanned is not None:
        return scanned

    # 3. last-resort: try the whole thing whitespace-stripped
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return None


def parse(raw: str) -> Union[
    IngestorReceipt, AnalystReceipt, ScorerReceipt, InfraScorerReceipt,
    ValidatorReceipt, BuilderReceipt, ClustererReceipt, MarketScoutReceipt,
    ReceiptError,
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
    # Stage 04 discriminator: the infra-node scorer receipt carries
    # `infra_nodes_scored`; the per-startup scorer receipt doesn't.
    if stage == "04" and _INFRA_SCORER_DISCRIMINATOR in payload:
        cls = InfraScorerReceipt
    try:
        return cls.model_validate(payload)
    except Exception as e:  # pydantic ValidationError carries rich details
        return ReceiptError(stage=stage, reason=str(e), raw=raw)