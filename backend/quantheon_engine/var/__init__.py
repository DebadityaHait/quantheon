# Modified by Quantheon contributors: renamed package imports.
"""
VaR module for portfolio Value-at-Risk calculations.
"""

from quantheon_engine.var.backtest import VaRBacktestResult, VaRBacktester
from quantheon_engine.var.base import VaREngine
from quantheon_engine.var.config import (
    EquityRiskFactorConfig,
    FIRiskFactorConfig,
    VaRConfig,
    VaRMethod,
)
from quantheon_engine.var.engines import (
    HistoricalVaREngine,
    MonteCarloVaREngine,
    ParametricVaREngine,
)
from quantheon_engine.var.fx import (
    FXHistoricalVaREngine,
    FXMonteCarloVaREngine,
    FXParametricVaREngine,
    FXRiskFactorConfig,
)
from quantheon_engine.var.credit import (
    CreditHistoricalVaREngine,
    CreditMonteCarloVaREngine,
    CreditParametricVaREngine,
    CreditRiskFactorConfig,
)
from quantheon_engine.var.results import IncrementalVaRResult, VaRResult
from quantheon_engine.var.results.var_report import VaRReportGenerator
from quantheon_engine.var.attribution import ComponentVaRCalculator, MarginalVaRCalculator, VaRAttributor

__all__ = [
    "VaREngine",
    "VaRConfig",
    "VaRMethod",
    "EquityRiskFactorConfig",
    "FIRiskFactorConfig",
    "VaRResult",
    "IncrementalVaRResult",
    "ParametricVaREngine",
    "HistoricalVaREngine",
    "MonteCarloVaREngine",
    "FXParametricVaREngine",
    "FXHistoricalVaREngine",
    "FXMonteCarloVaREngine",
    "FXRiskFactorConfig",
    "CreditParametricVaREngine",
    "CreditHistoricalVaREngine",
    "CreditMonteCarloVaREngine",
    "CreditRiskFactorConfig",
    "VaRBacktester",
    "VaRBacktestResult",
    "VaRReportGenerator",
    "ComponentVaRCalculator",
    "MarginalVaRCalculator",
    "VaRAttributor",
]