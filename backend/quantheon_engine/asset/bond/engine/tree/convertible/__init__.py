# Modified by Quantheon contributors: renamed package imports.
"""
Tree-based pricing engines for convertible bonds.

This module provides:
- ConvertibleBondTreeParams: Configuration for tree-based pricing
- ConvertibleBondBinomialEngine: Goldman Sachs credit-adjusted binomial model
- ConvertibleBondTrinomialEngine: Hull-White trinomial model with default
"""
from quantheon_engine.asset.bond.engine.tree.convertible.tree_params import ConvertibleBondTreeParams
from quantheon_engine.asset.bond.engine.tree.convertible.binomial_engine import (
    ConvertibleBondBinomialEngine,
)
from quantheon_engine.asset.bond.engine.tree.convertible.trinomial_engine import (
    ConvertibleBondTrinomialEngine,
)

__all__ = [
    "ConvertibleBondTreeParams",
    "ConvertibleBondBinomialEngine",
    "ConvertibleBondTrinomialEngine",
]
