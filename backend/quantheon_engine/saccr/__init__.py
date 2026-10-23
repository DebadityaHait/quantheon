# Modified by Quantheon contributors: renamed package imports.
"""SA-CCR (Standardised Approach for Counterparty Credit Risk) calculator.

Implements the Basel Committee SA-CCR methodology for Exposure at Default (EAD)
on derivative netting sets: ``EAD = alpha x (RC + PFE)``. See
``quantheon_engine/saccr/doc/saccr_basel.md`` for the methodology reference and
``quantheon_engine/saccr/CLAUDE.md`` for the developer guide.

Reference: Basel Committee on Banking Supervision, "The standardised approach for
measuring counterparty credit risk exposures" (BCBS d291, Mar 2014, rev Apr 2014).
"""

from quantheon_engine.saccr.calculator import SACCRCalculator
from quantheon_engine.saccr.results.result import SACCRResult
from quantheon_engine.saccr.models.trade import SACCRTrade
from quantheon_engine.saccr.models.netting_set import SACCRNettingSet
from quantheon_engine.saccr.models.enums import (
    AssetClass,
    Position,
    CreditRating,
    IndexGrade,
    CommodityHedgingSet,
    CommodityType,
    TransactionType,
)
from quantheon_engine.saccr.parameters.supervisory import SACCR_VERSION
from quantheon_engine.saccr.dashboard import SACCRDashboard
from quantheon_engine.util.enum.option_enums import OptionType

__version__ = SACCR_VERSION

__all__ = [
    "SACCRCalculator",
    "SACCRResult",
    "SACCRTrade",
    "SACCRNettingSet",
    "AssetClass",
    "Position",
    "CreditRating",
    "IndexGrade",
    "CommodityHedgingSet",
    "CommodityType",
    "TransactionType",
    "OptionType",
    "SACCRDashboard",
    "SACCR_VERSION",
]
