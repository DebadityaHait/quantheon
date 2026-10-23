# Modified by Quantheon contributors: renamed package imports.
"""Quantheon Engine composable execution kernel (framework contract v1, Phases 0-6).

Additive public surface (spec section 5). Direct legacy engine calls are
unchanged; this package is reached only through explicit sessions or
``BaseEngine.execute``.
"""
from quantheon_engine.execution.api import PricingSession
from quantheon_engine.execution.cache.draws import DrawRepository
from quantheon_engine.execution.capability_matrix import render_capability_matrix
from quantheon_engine.execution.context import PricingRunContext, default_context
from quantheon_engine.execution.contracts import (
    DEFAULT_OUTPUTS,
    AdaptivePlan,
    BatchOutcome,
    BatchPlan,
    BatchTask,
    EngineCapabilities,
    FrameworkErrorInfo,
    NormalizedPricingRequest,
    OutputKind,
    PricingFailure,
    PricingOperation,
    PricingOutcome,
    PricingRequest,
    ScenarioOutcome,
    ScenarioSpec,
)
from quantheon_engine.execution.greeks import (
    GREEK_BUMP_TRANSFORMER_ID,
    GREEK_VALUE_RUNNER_ID,
    GreekBumpCell,
    TradeState,
    apply_greek_bump,
    assemble_product_greeks,
    assemble_trade_greeks,
    greek_bump_cells,
)
from quantheon_engine.execution.errors import (
    CapabilityError,
    DeterminismViolation,
    PreparationError,
    ResourceBudgetExceeded,
    TaskExecutionError,
    ValidationGateError,
)
from quantheon_engine.execution.policy import (
    DeterminismPolicy,
    ExecutionPolicy,
    ExecutorSelection,
    ResourceBudget,
)
from quantheon_engine.execution.scenario.contracts import (
    BaseInputsRef,
    CallableRef,
    ScenarioCell,
    ScenarioPlan,
    WorkerSpec,
)
from quantheon_engine.execution.scenario.planner import plan_scenarios
from quantheon_engine.execution.scenario.validate import (
    ScenarioComparisonReport,
    compare_scenario_outcomes,
)

__all__ = [
    "AdaptivePlan",
    "BaseInputsRef",
    "BatchOutcome",
    "BatchPlan",
    "BatchTask",
    "CallableRef",
    "CapabilityError",
    "DEFAULT_OUTPUTS",
    "GREEK_BUMP_TRANSFORMER_ID",
    "GREEK_VALUE_RUNNER_ID",
    "GreekBumpCell",
    "TradeState",
    "apply_greek_bump",
    "assemble_product_greeks",
    "assemble_trade_greeks",
    "greek_bump_cells",
    "DeterminismPolicy",
    "DeterminismViolation",
    "DrawRepository",
    "EngineCapabilities",
    "ExecutionPolicy",
    "ExecutorSelection",
    "FrameworkErrorInfo",
    "NormalizedPricingRequest",
    "OutputKind",
    "PreparationError",
    "PricingFailure",
    "PricingOperation",
    "PricingOutcome",
    "PricingRequest",
    "PricingRunContext",
    "PricingSession",
    "ResourceBudget",
    "ResourceBudgetExceeded",
    "ScenarioCell",
    "ScenarioComparisonReport",
    "ScenarioOutcome",
    "ScenarioPlan",
    "ScenarioSpec",
    "TaskExecutionError",
    "ValidationGateError",
    "WorkerSpec",
    "compare_scenario_outcomes",
    "default_context",
    "plan_scenarios",
    "render_capability_matrix",
]
