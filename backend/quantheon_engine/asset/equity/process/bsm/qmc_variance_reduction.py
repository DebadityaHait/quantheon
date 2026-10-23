# Modified by Quantheon contributors: renamed package imports.
"""Back-compat shim. Canonical home: quantheon_engine.montecarlo.qmc_variance_reduction."""
from quantheon_engine.montecarlo.qmc_variance_reduction import *  # noqa: F401,F403
from quantheon_engine.montecarlo.qmc_variance_reduction import (  # noqa: F401
    VarianceReductionConfig,
    build_antithetic_pairs,
    apply_importance_sampling_shift,
    importance_sampling_weights,
    gbm_control_variate,
    apply_variance_reduction_to_normals,
)
from quantheon_engine.montecarlo.qmc_variance_reduction import __all__  # noqa: F401
