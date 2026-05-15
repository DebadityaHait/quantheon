"""Representation-specific checks; native kwargs never acquire market fields."""
from __future__ import annotations

import math
from typing import Any, Literal

Representation = Literal["raw_build_inputs", "native_product_terms", "valuation_market"]


def check_valuation_market(market: dict[str, Any]) -> dict[str, Any]:
    required = ("spot", "volatility", "rate", "dividend_yield", "valuation_date")
    missing = [key for key in required if market.get(key) in (None, "")]
    errors = []
    for key in required[:-1]:
        if key in missing:
            continue
        value = market[key]
        try:
            if isinstance(value, bool) or not math.isfinite(float(value)):
                raise ValueError
            if key in {"spot", "volatility"} and float(value) <= 0:
                raise ValueError
        except (ValueError, TypeError):
            errors.append(f"{key} must be finite" + (" and positive" if key in {"spot", "volatility"} else ""))
    if "valuation_date" not in missing:
        from datetime import datetime
        try:
            datetime.fromisoformat(str(market["valuation_date"]).replace("Z", "+00:00"))
        except ValueError:
            errors.append("valuation_date must be an ISO date or timestamp")
    return {"representation": "valuation_market", "complete": not missing and not errors,
            "missing_required": missing, "provided_required": [key for key in required if key not in missing],
            "defaulted_unset": [], "conflicts": [], "errors": errors,
            "note": "Market completeness is separate from product-term validity; historical source evidence must also be verified."}


def check_native_terms(family: str, terms: dict[str, Any]) -> dict[str, Any]:
    # Use the installed registry's real constructor conversion and validation,
    # including nested configs and schedules. No raw-input resynthesis or price.
    from app.services.quantark import _ensure_sharkfin_registry_support
    _ensure_sharkfin_registry_support()
    from quantark.rfq.builders import build_product_from_termsheet
    import inspect
    from quantark.asset.equity.product import option, deltaone
    cls = getattr(option, family, None) or getattr(deltaone, family, None)
    missing: list[str] = []
    if cls is not None:
        params = inspect.signature(cls).parameters
        missing = [name for name, p in params.items()
                   if p.default is inspect.Parameter.empty and p.kind not in
                   {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
                   and terms.get(name) is None]
        if "maturity" in params and "exercise_date" in params and not any(
            terms.get(key) is not None for key in ("maturity", "exercise_date")
        ):
            missing.append("maturity|exercise_date")
    errors: list[str] = []
    try:
        from app.schemas import PricingEnvironmentSnapshot
        from app.services.quantark import _build_termsheet
        from .product_builders import _ENGINE_BY_CLASS
        sheet, _ = _build_termsheet(product_type=family, product_kwargs=dict(terms),
                                    market=PricingEnvironmentSnapshot(),
                                    engine_name=_ENGINE_BY_CLASS.get(family, "BlackScholesEngine"), engine_kwargs=None)
        build_product_from_termsheet(sheet)
    except Exception as exc:
        errors.append(str(exc))
    return {"quantark_class": family, "representation": "native_product_terms",
            "complete": not missing and not errors, "missing_required": missing,
            "provided_required": [], "defaulted_unset": [], "conflicts": [], "errors": errors,
            "validation": {"ok": not missing and not errors, "scope": "native_product_constructor"},
            "note": "Native constructor terms only. Validation spot/fixing provenance belongs outside kwargs; pricing requires a separately validated valuation market."}
