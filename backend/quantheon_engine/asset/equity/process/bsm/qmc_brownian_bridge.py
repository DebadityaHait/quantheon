# Modified by Quantheon contributors: renamed package imports.
"""Back-compat shim. Canonical home: quantheon_engine.montecarlo.qmc_brownian_bridge."""
from quantheon_engine.montecarlo.qmc_brownian_bridge import *  # noqa: F401,F403
from quantheon_engine.montecarlo.qmc_brownian_bridge import (  # noqa: F401
    BrownianBridge,
    apply_brownian_bridge,
    apply_brownian_bridge_multi_asset,
    compute_step_crossing_probabilities,
    compute_barrier_crossing_probabilities,
)
from quantheon_engine.montecarlo.qmc_brownian_bridge import __all__  # noqa: F401
