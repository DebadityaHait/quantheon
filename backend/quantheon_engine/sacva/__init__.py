# Modified by Quantheon contributors: renamed package imports.
"""SA-CVA — Basel standardised approach for CVA risk (MAR50.27-50.77).

Aggregates supplied CVA and hedge sensitivities into delta + vega capital. The
module consumes sensitivities (MAR50.29); it does not compute CVA itself.
See ``quantheon_engine/sacva/doc/sacva_basel.md`` and the design spec.
"""

from quantheon_engine.sacva.calculator import SACVACalculator
from quantheon_engine.sacva.results.result import SACVAResult
from quantheon_engine.sacva.models.enums import RiskClass, RiskType, CreditQuality
from quantheon_engine.sacva.models.sensitivity import CVASensitivity
from quantheon_engine.sacva.models.portfolio import CVAPortfolio
from quantheon_engine.sacva.parameters.supervisory import SACVA_VERSION
from quantheon_engine.sacva.dashboard import SACVADashboard

# portfolio/engine integration: compute CVA + sensitivities from a real portfolio
from quantheon_engine.sacva.sacva_engine import SACVAEngine
from quantheon_engine.sacva.exposure.simulator import (
    MonteCarloExposureConfig,
    MonteCarloExposureEngine,
)
from quantheon_engine.sacva.cva.engine import RegulatoryCVAEngine
from quantheon_engine.sacva.exposure.historical.engine import (
    HistoricalExposureConfig,
    HistoricalExposureEngine,
)
from quantheon_engine.sacva.sensitivities.engine import CVASensitivityEngine
from quantheon_engine.sacva.portfolio.trade import CVAHedge, CVATrade
from quantheon_engine.sacva.portfolio.netting import NettingSet
from quantheon_engine.sacva.portfolio.counterparty import Counterparty
from quantheon_engine.sacva.portfolio.trade_portfolio import CVATradePortfolio
from quantheon_engine.sacva.portfolio.credit_curve import PillarHazardCurve

__version__ = SACVA_VERSION

__all__ = [
    "SACVACalculator", "SACVAResult", "CVASensitivity", "CVAPortfolio",
    "RiskClass", "RiskType", "CreditQuality", "SACVADashboard", "SACVA_VERSION",
    # portfolio/engine integration
    "SACVAEngine", "MonteCarloExposureEngine", "MonteCarloExposureConfig",
    "RegulatoryCVAEngine", "CVASensitivityEngine", "CVATrade", "CVAHedge",
    "NettingSet", "Counterparty", "CVATradePortfolio", "PillarHazardCurve",
    # non-regulatory real-world PFE/EE (never SA-CVA eligible)
    "HistoricalExposureEngine", "HistoricalExposureConfig",
]
