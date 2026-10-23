# Modified by Quantheon contributors: renamed package imports.
"""Asset-neutral volatility-model kernels (Local Vol, Heston, SLV).

These modules operate on plain numeric primitives and a generic cost-of-carry
``b = r - carry`` (carry = dividend yield for equity, foreign rate for FX). They
import no asset products and no pricing environments. Import subpackages directly,
e.g. ``from quantheon_engine.volmodels.black_scholes import bs_call_price``.
"""
