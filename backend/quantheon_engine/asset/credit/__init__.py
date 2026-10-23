# Modified by Quantheon contributors: renamed package imports.
"""Credit derivatives asset class (CDS, basket CDS)."""
from quantheon_engine.asset.credit.product import (
    CDS,
    ProtectionSide,
    BasketCDS,
    BasketType,
    CopulaType,
)
from quantheon_engine.asset.credit.engine.analytical import CDSReducedFormEngine
from quantheon_engine.asset.credit.engine.mc import BasketCDSEngine

__all__ = [
    "CDS",
    "ProtectionSide",
    "BasketCDS",
    "BasketType",
    "CopulaType",
    "CDSReducedFormEngine",
    "BasketCDSEngine",
]
