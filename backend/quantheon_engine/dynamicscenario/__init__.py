# Modified by Quantheon contributors: renamed package imports.
"""
Dynamic Scenario Analysis module for multi-day stress testing with hedging.

This module provides tools for simulating portfolio evolution over multi-day
market scenarios with optional hedging strategies. Supports both equity and
fixed income portfolios.

Key components:
- DayPath: Defines market parameter evolution over days
- PathBuilder: Fluent API for constructing day paths
- PathLibrary: Predefined path patterns (rally, decline, etc.)
- FIPathLibrary: FI-specific path patterns (rate hikes, curve twists, etc.)
- DynamicScenarioEngine: Main engine for running simulations (equity)
- FIDynamicScenarioEngine: FI-specific engine
- DynamicScenarioResults: Results with day-by-day evolution
- FIDynamicScenarioResults: FI-specific results with DV01/duration tracking
"""

# Base protocols
from quantheon_engine.dynamicscenario.base import (
    BaseDynamicScenarioEngine,
    BaseScenarioResults,
    BaseDayResult,
    RiskMetricsAdapter,
    get_engine_for_portfolio,
)

# Path components
from quantheon_engine.dynamicscenario.path.day_path import DayStep, DayPath, ParameterChange
from quantheon_engine.dynamicscenario.path.path_builder import PathBuilder
from quantheon_engine.dynamicscenario.path.path_library import PathLibrary

# Equity (default) components
from quantheon_engine.dynamicscenario.config import DynamicScenarioConfig
from quantheon_engine.dynamicscenario.engine import DynamicScenarioEngine
from quantheon_engine.dynamicscenario.results.dynamic_results import (
    DayResult,
    DynamicScenarioResults,
    PositionSnapshot,
    TradeSnapshot,
    MarketState,
    LifecycleEventSnapshot,
)
from quantheon_engine.dynamicscenario.results.result_exporter import DynamicResultExporter
from quantheon_engine.dynamicscenario.report.dynamic_report import DynamicReportGenerator
from quantheon_engine.dynamicscenario.lifecycle_manager import LifecycleManager
from quantheon_engine.dynamicscenario.report.visualizer import DynamicScenarioVisualizer

# FI path library
from quantheon_engine.dynamicscenario.path.fi_path_library import FIPathLibrary

# FI components
from quantheon_engine.dynamicscenario.fi import (
    FIDynamicScenarioConfig,
    FIDynamicScenarioEngine,
    FIDayResult,
    FIDynamicScenarioResults,
    FIMarketState,
    FITradeSnapshot,
)

# FX components
from quantheon_engine.dynamicscenario.fx import (
    FXDynamicScenarioConfig,
    FXDynamicScenarioEngine,
    FXRiskMetricsAdapter,
    FXPathLibrary,
)

# Credit components
from quantheon_engine.dynamicscenario.credit import (
    CreditDynamicScenarioConfig,
    CreditDynamicScenarioEngine,
    CreditRiskMetricsAdapter,
    CreditPathLibrary,
)

__all__ = [
    # Base protocols
    "BaseDynamicScenarioEngine",
    "BaseScenarioResults",
    "BaseDayResult",
    "RiskMetricsAdapter",
    "get_engine_for_portfolio",
    # Path components
    "DayStep",
    "DayPath",
    "ParameterChange",
    "PathBuilder",
    "PathLibrary",
    "FIPathLibrary",
    # Equity config
    "DynamicScenarioConfig",
    # Equity engine
    "DynamicScenarioEngine",
    # Equity results
    "DayResult",
    "DynamicScenarioResults",
    "PositionSnapshot",
    "TradeSnapshot",
    "MarketState",
    "DynamicResultExporter",
    # Lifecycle
    "LifecycleManager",
    "LifecycleEventSnapshot",
    # Report & Visualization
    "DynamicReportGenerator",
    "DynamicScenarioVisualizer",
    # FI config
    "FIDynamicScenarioConfig",
    # FI engine
    "FIDynamicScenarioEngine",
    # FI results
    "FIDayResult",
    "FIDynamicScenarioResults",
    "FIMarketState",
    "FITradeSnapshot",
    # FX
    "FXDynamicScenarioConfig",
    "FXDynamicScenarioEngine",
    "FXRiskMetricsAdapter",
    "FXPathLibrary",
    # Credit
    "CreditDynamicScenarioConfig",
    "CreditDynamicScenarioEngine",
    "CreditRiskMetricsAdapter",
    "CreditPathLibrary",
]
