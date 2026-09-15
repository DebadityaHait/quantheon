"""Seeded run payloads must reference the rows the SAME seed inserted.

A risk run seeded with ``metrics.positions[].position_id`` copied from the clean DB
the truth was harvested in points at ids 1..N. A clean test DB hands out exactly
those ids, so every unit test passes — but the live arena DB autoincrements, so the
"governed" run covered positions the book did not hold. high-board shipped that way
(run #146: the only model that noticed refused to answer from it, and was the only
``nvda_delta`` failure in 97 trials). Hence two halves: a STATIC lint that a literal
id is never written at all, and a DYNAMIC check that each token lands on a seeded
row with the same underlying.
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from app.golden_workflows.registry import list_workflow_bundles

# Keys inside a seeded run payload that name a row by primary key, and the seed
# namespace that row must come from.
_ID_KEYS = {
    "position_id": "positions",
    "pricing_parameter_row_id": "pricing_parameter_rows",
    "market_quote_id": "market_quotes",
}
_ID_LIST_SUFFIX = "_position_ids"
_RUN_NAMESPACES = ("risk_runs", "valuation_runs")


def _references(node, path=""):
    """Yield (path, key, value, namespace) for every row reference in ``node``."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}"
            if key in _ID_KEYS and value is not None:
                yield here, key, value, _ID_KEYS[key]
            elif key.endswith(_ID_LIST_SUFFIX) and isinstance(value, list):
                for i, item in enumerate(value):
                    yield f"{here}[{i}]", key, item, "positions"
            else:
                yield from _references(value, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from _references(item, f"{path}[{i}]")


def _seeded_runs(bundle):
    for ns in _RUN_NAMESPACES:
        for row in bundle.fixtures.seed.get(ns, []) or []:
            yield ns, row


_BUNDLES = [
    pytest.param(b, id=b.workflow.id)
    for b in list_workflow_bundles()
    if any(True for _ in _seeded_runs(b))
]


@pytest.mark.parametrize("bundle", _BUNDLES)
def test_seeded_run_payloads_use_seed_tokens_not_literal_ids(bundle):
    aliases = {
        ns: {row["alias"] for row in rows or [] if "alias" in row}
        for ns, rows in bundle.fixtures.seed.items()
    }
    problems = []
    for ns, run in _seeded_runs(bundle):
        for path, _, value, target_ns in _references(run, f"{ns}[{run.get('alias')}]"):
            if not (isinstance(value, str) and value.startswith(f"$seed.{target_ns}.")):
                problems.append(f"{path} = {value!r} (expected a $seed.{target_ns}.<alias>.id token)")
                continue
            alias = value.split(".")[2]
            if alias not in aliases.get(target_ns, set()):
                problems.append(f"{path} = {value!r} names no seeded {target_ns} alias")
    assert not problems, "\n".join(problems)


_BURNED_ID = 700


def _burn_ids(session) -> None:
    """Occupy ids well above 1 so seeded rows autoincrement past them, like the live
    arena DB. In a clean DB the seed lands on ids 1..N, which is exactly where a
    harvested literal points — the dynamic check would pass by coincidence."""
    from app import models

    book = models.Portfolio(name="__id_burner__", base_currency="USD",
                            kind=models.PortfolioKind.CONTAINER.value)
    session.add(book)
    session.flush()
    session.add(models.Position(id=_BURNED_ID, portfolio_id=book.id, underlying="BURN",
                                product_type="EuropeanVanillaOption", quantity=1.0))
    profile = models.PricingParameterProfile(name="__id_burner__",
                                             valuation_date=datetime(2026, 1, 1))
    session.add(profile)
    session.flush()
    session.add(models.PricingParameterRow(id=_BURNED_ID, profile_id=profile.id,
                                           source_trade_id="burn", symbol="BURN"))
    session.commit()


@pytest.mark.parametrize("bundle", _BUNDLES)
def test_seeded_run_positions_resolve_to_same_underlying(bundle, session):
    from app import models
    from app.golden_workflows.fixtures import apply_seed

    _burn_ids(session)
    ids = apply_seed(bundle.fixtures, session)
    symbol_by_ppr = {
        r.id: r.symbol
        for r in session.query(models.PricingParameterRow).filter(
            models.PricingParameterRow.id.in_(list(ids.get("pricing_parameter_rows", {}).values()))
        )
    }
    seeded_pids = set(ids.get("portfolios", {}).values())
    underlying_by_id = {
        p.id: p.underlying
        for p in session.query(models.Position).filter(
            models.Position.id.in_(list(ids.get("positions", {}).values()))
        )
    }
    runs = session.query(models.RiskRun).filter(models.RiskRun.portfolio_id.in_(seeded_pids)).all()
    assert runs, "fixture declares a risk run but none was seeded"
    for run in runs:
        rows = (run.metrics or {}).get("positions") or []
        for row in rows:
            pid = row.get("position_id")
            assert pid in underlying_by_id, f"risk run {run.id} row {row.get('underlying')} -> position {pid} not seeded"
            assert underlying_by_id[pid] == row.get("underlying"), (
                f"risk run {run.id}: position {pid} is {underlying_by_id[pid]}, row says {row.get('underlying')}"
            )
            ppr = row.get("pricing_parameter_row_id")
            if ppr is not None:
                assert symbol_by_ppr.get(ppr) == row.get("underlying"), (
                    f"risk run {run.id}: pricing_parameter_row {ppr} is not the seeded "
                    f"{row.get('underlying')} row"
                )
        coverage = (run.metrics or {}).get("coverage") or {}
        for key, value in coverage.items():
            if key.endswith(_ID_LIST_SUFFIX):
                assert set(value) <= set(underlying_by_id), f"coverage.{key} = {json.dumps(value)} not seeded"
    for vrun in session.query(models.PositionValuationRun).filter(
        models.PositionValuationRun.portfolio_id.in_(seeded_pids)
    ):
        assert set(vrun.resolved_position_ids or []) <= set(underlying_by_id), vrun.resolved_position_ids
        for result in vrun.results:
            assert result.position_id in underlying_by_id, f"valuation {vrun.id} -> position {result.position_id}"
            ppr = (result.market_inputs or {}).get("pricing_parameter_row_id")
            if ppr is not None:
                assert symbol_by_ppr.get(ppr) == underlying_by_id[result.position_id]
    for run in runs:
        coverage = (run.metrics or {}).get("coverage") or {}
        for key, value in coverage.items():
            if key.endswith(_ID_LIST_SUFFIX):
                assert set(value) <= set(underlying_by_id), f"coverage.{key} = {json.dumps(value)} not seeded"
