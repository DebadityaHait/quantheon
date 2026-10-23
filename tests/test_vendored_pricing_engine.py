"""The desk ships its pricing engine rather than requiring a second distribution."""
from pathlib import Path

import quantheon_engine

from app.services.arena import provenance


def test_pricing_engine_is_the_vendored_release():
    root = Path(__file__).resolve().parents[1]
    assert Path(quantheon_engine.__file__).resolve().is_relative_to(root / "backend" / "quantheon_engine")
    assert quantheon_engine.__version__ == "0.3.0"


def test_legacy_service_symbols_remain_compatible():
    from app.services import quantheon_engine as service
    from app.services.domains import products

    assert service.QuantArkResult is service.EngineResult
    assert service.ensure_quantark_path is service.ensure_engine_path
    assert service.normalize_quantark_kwargs is service.normalize_engine_kwargs
    assert service.validate_quantark_build is service.validate_engine_build
    assert products.product_family_for_quantark_class is products.product_family_for_engine_class


def test_provenance_reports_the_loaded_engine_version(monkeypatch):
    monkeypatch.setattr(quantheon_engine, "__version__", "test-loaded-engine")
    assert provenance._package("quantark") == "test-loaded-engine"
