# Modified by Quantheon contributors: renamed package imports.
"""
SIMM Sensitivity Engines

This module provides sensitivity calculation engines for ISDA SIMM (Standard Initial Margin Model) v2.6.

The engines follow a protocol-based architecture with support for:
- Interest Rate sensitivities (delta, vega, curvature)
- Equity sensitivities (delta, vega)
- Portfolio-to-sensitivity conversion
- CRIF format import/export
- Full SIMM aggregation (concentration, bucket, risk class, product class)
"""

from quantheon_engine.simm.engines.base import (
    SensitivityEngine,
    BaseSensitivityEngine,
    SIMMSensitivityProvider,
)
from quantheon_engine.simm.engines.factory import create_engine
from quantheon_engine.simm.engines.portfolio_adapter import SIMMPortfolioAdapter
from quantheon_engine.simm.engines.result import SIMMResult

# Aggregation engine exports
from quantheon_engine.simm.engines.aggregation import (
    SIMMCalculator,
    SIMMAggregationResult,
    ConcentrationCalculator,
    ConcentrationResult,
    WeightedSensitivityCalculator,
    WeightedSensitivity,
    BucketAggregator,
    BucketResult,
    RiskClassAggregator,
    RiskClassResult,
    ProductClassAggregator,
    ProductClassResult,
    AddOnCalculator,
    AddOnResult,
)

__all__ = [
    # Base engine classes
    "SensitivityEngine",
    "BaseSensitivityEngine",
    "SIMMSensitivityProvider",
    "create_engine",
    "SIMMPortfolioAdapter",
    "SIMMResult",
    # Aggregation engine
    "SIMMCalculator",
    "SIMMAggregationResult",
    "ConcentrationCalculator",
    "ConcentrationResult",
    "WeightedSensitivityCalculator",
    "WeightedSensitivity",
    "BucketAggregator",
    "BucketResult",
    "RiskClassAggregator",
    "RiskClassResult",
    "ProductClassAggregator",
    "ProductClassResult",
    "AddOnCalculator",
    "AddOnResult",
]
