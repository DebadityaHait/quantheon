# Modified by Quantheon contributors: renamed package imports.
"""
Strategy framework for backtesting.

Includes abstract base strategy and concrete implementations for:
- Equity: delta-neutral, Whalley-Wilmott band, minimum-variance delta,
  and multi-Greek (delta+gamma, delta+vega, delta+gamma+vega) hedging
- Fixed Income: DV01-neutral and convexity-neutral hedging
"""

from quantheon_engine.backtest.strategy.base_strategy import (
    BaseStrategy,
    AssetClass,
    HedgingTarget,
    passes_frequency_gate,
)
from quantheon_engine.backtest.strategy.delta_neutral_strategy import DeltaNeutralStrategy
from quantheon_engine.backtest.strategy.dv01_neutral_strategy import DV01NeutralStrategy
from quantheon_engine.backtest.strategy.convexity_neutral_strategy import ConvexityNeutralStrategy
from quantheon_engine.backtest.strategy.fx_delta_neutral_strategy import FXDeltaNeutralStrategy
from quantheon_engine.backtest.strategy.credit_spread_neutral_strategy import CreditSpreadNeutralStrategy
from quantheon_engine.backtest.strategy.hedge_optimizer import HedgeOptimizer, HedgeTarget
from quantheon_engine.backtest.strategy.hedge_instruments import (
    BaseHedgeInstrument,
    SpotHedgeInstrument,
    FuturesHedgeInstrument,
    OptionHedgeInstrument,
)
from quantheon_engine.backtest.strategy.multi_greek_strategy import (
    MultiGreekHedgeStrategy,
    DeltaGammaNeutralStrategy,
    DeltaVegaNeutralStrategy,
    DeltaGammaVegaNeutralStrategy,
)
from quantheon_engine.backtest.strategy.whalley_wilmott_strategy import WhalleyWilmottStrategy
from quantheon_engine.backtest.strategy.min_variance_delta_strategy import (
    MinimumVarianceDeltaStrategy,
)
from quantheon_engine.backtest.strategy.scenarios import (
    MarketScenario,
    apply_scenario,
    instrument_scenario_pnl,
    portfolio_scenario_pnl,
)
from quantheon_engine.backtest.strategy.scenario_hedge_strategy import ScenarioHedgeStrategy
from quantheon_engine.backtest.strategy.semi_static_strategy import SemiStaticHedgeStrategy
from quantheon_engine.backtest.strategy.barrier_trigger_strategy import (
    BarrierTriggerHedgeStrategy,
)
from quantheon_engine.backtest.strategy.triggered_hedge_strategy import (
    HedgeTrigger,
    TriggeredHedgeStrategy,
)

__all__ = [
    # Base
    'BaseStrategy',
    'AssetClass',
    'HedgingTarget',
    'passes_frequency_gate',
    # Equity strategies
    'DeltaNeutralStrategy',
    'WhalleyWilmottStrategy',
    'MinimumVarianceDeltaStrategy',
    # Multi-Greek hedging
    'HedgeOptimizer',
    'HedgeTarget',
    'BaseHedgeInstrument',
    'SpotHedgeInstrument',
    'FuturesHedgeInstrument',
    'OptionHedgeInstrument',
    'MultiGreekHedgeStrategy',
    'DeltaGammaNeutralStrategy',
    'DeltaVegaNeutralStrategy',
    'DeltaGammaVegaNeutralStrategy',
    # Event/scenario/barrier hedging
    'MarketScenario',
    'apply_scenario',
    'instrument_scenario_pnl',
    'portfolio_scenario_pnl',
    'ScenarioHedgeStrategy',
    'SemiStaticHedgeStrategy',
    'BarrierTriggerHedgeStrategy',
    'HedgeTrigger',
    'TriggeredHedgeStrategy',
    # Fixed Income strategies
    'DV01NeutralStrategy',
    'ConvexityNeutralStrategy',
    # FX strategies
    'FXDeltaNeutralStrategy',
    # Credit strategies
    'CreditSpreadNeutralStrategy',
]
