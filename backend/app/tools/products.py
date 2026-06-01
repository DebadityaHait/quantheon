"""@tool wrapper for deterministic product construction."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from app.schemas import PricingEnvironmentSnapshot
from app.services.deep_agent.capability_gate import capability_gated
from app.services.deep_agent.envelopes import ToolGroup
from app.services.domains.product_builders import build_product


class FixingReference(BaseModel):
    artifact_id: int = Field(gt=0)
    fixing_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

class BuildProductInput(BaseModel):
    family: str = Field(description="QuantArk product class, e.g. 'SnowballOption'.")
    terms: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured per-family terms (levels, frequencies, tenor, dates).",
    )
    underlying: str | None = None
    currency: str | None = None
    market: PricingEnvironmentSnapshot | None = None
    fixing_references: list[FixingReference] = Field(default_factory=list, description="Captured snapshot artifact IDs and requested fixing dates. Verified outside native terms; never insert these into kwargs.")


@capability_gated(group=ToolGroup.DOMAIN_READ)
@tool("build_product", args_schema=BuildProductInput)
def build_product_tool(family: str, terms: dict[str, Any], underlying: str | None = None,
                       currency: str | None = None, market: PricingEnvironmentSnapshot | None = None,
                       fixing_references: list[FixingReference] | None = None,
                       config: RunnableConfig = None) -> dict[str, Any]:
    """Construct a quant-ark-validated product from structured terms.

    Synthesizes observation schedules where required. Reports any economics it
    will not invent (lockup, trade start, barrier levels, coupon) in `missing`
    instead of guessing. Does not book a trade. The runtime saves an exact build
    receipt for progressive retrieval. Returned product_spec.source_payload
    carries provenance outside native constructor terms; pass it to RFQ/booking.
    """
    from dataclasses import replace
    from app.services.domains.build_provenance import resolve_fixing_references
    result = build_product(family, dict(terms or {}), underlying=underlying, currency=currency, market=market)
    spec = result.product_spec
    if spec:
        refs = resolve_fixing_references(
            [r.model_dump() if hasattr(r, "model_dump") else r for r in fixing_references or []],
            config=config, underlying=underlying or terms.get("underlying") or "UNKNOWN",
            initial_price=terms.get("initial_price"),
        ) if fixing_references else []
        source = dict(spec.source_payload or {})
        source["build_provenance"]["fixing_references"] = refs
        spec = replace(spec, source_payload=source)
    return {
        "ok": result.ok,
        "quantark_class": result.quantark_class,
        "engine_name": result.engine_name,
        "product_kwargs": result.product_kwargs,
        "missing": result.missing,
        "warnings": result.warnings,
        "validation": result.validation,
        "representation": "raw_build_inputs",
        "output_representation": "native_product_terms",
        "product_spec": asdict(spec) if spec else None,
    }


__all__ = ["build_product_tool"]
