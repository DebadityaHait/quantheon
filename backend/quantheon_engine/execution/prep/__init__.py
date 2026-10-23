# Modified by Quantheon contributors: renamed package imports.
"""Shared preparation artifact states for engine-family adapters.

These helpers sit BETWEEN the execution kernel and the engine families: the
kernel never imports them (adapters do), and they import only shared model
infrastructure (``quantheon_engine.volmodels``), following the precedent of
``execution.cache.draws`` importing ``quantheon_engine.montecarlo``.
"""
from quantheon_engine.execution.prep.dupire import dupire_surface_state

__all__ = ["dupire_surface_state"]
