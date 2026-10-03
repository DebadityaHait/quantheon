"""The provider tier of `scripts/refresh_model_reasoning.py`.

The merge MECHANICS are tested with `provider_ladder` stubbed, so they hold
whatever policy decides a declared ladder's final shape; that policy has its own
tests below.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def refresh():
    """Load the script by PATH — `scripts/` has no __init__.py."""
    spec = importlib.util.spec_from_file_location(
        "refresh_model_reasoning", _ROOT / "scripts" / "refresh_model_reasoning.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def declared_only(refresh, monkeypatch):
    """Stub the ladder policy: record exactly what the vendor declared."""
    monkeypatch.setattr(refresh, "provider_ladder", lambda declared, existing: declared)
    return refresh


SEVEN = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]
DEEPSEEK_MODELS = [
    {"id": "deepseek-flash",
     "effort": {"supported_levels": ["low", "high", "max"], "default_level": "high"}},
    {"id": "no-effort-block"},
]


def _measured(efforts=SEVEN, **extra):
    return {"reasoning": True, "efforts": list(efforts), "toggle": False,
            "source": "measured", "measured_at": "2026-09-25", **extra}


def test_merge_provider_overlays_the_declared_ladder(declared_only):
    snap = {"routes": {"deepseek": {"deepseek-v4-flash": _measured(
        interleaved_field="reasoning_content")}}}
    out = declared_only.merge_provider(
        snap, DEEPSEEK_MODELS,
        {("deepseek", "deepseek-v4-flash"): "deepseek-flash"}, "2026-09-30")
    entry = out["routes"]["deepseek"]["deepseek-v4-flash"]
    assert entry["efforts"] == ["low", "high", "max"]
    assert entry["source"] == "provider"
    assert entry["provider_model"] == "deepseek-flash"
    assert entry["provider_default"] == "high"
    assert entry["declared_at"] == "2026-09-30"
    assert "measured_at" not in entry
    # Facts the provider does not speak to are kept.
    assert entry["interleaved_field"] == "reasoning_content"


def test_a_pinned_route_inherits_its_unpinned_twins_facts(declared_only):
    """The ZenMux key is the `:deepseek` PIN, which has no entry of its own; the
    merge must start from the unpinned twin, as `effort_support` would."""
    seen = {}

    def spy(declared, existing):
        seen["existing"] = existing
        return declared

    declared_only.provider_ladder = spy
    snap = {"routes": {"zenmux": {"deepseek/deepseek-v4.1-flash": _measured()}}}
    out = declared_only.merge_provider(
        snap, DEEPSEEK_MODELS,
        {("zenmux", "deepseek/deepseek-v4.1-flash:deepseek"): "deepseek-flash"},
        "2026-09-30")
    assert seen["existing"]["efforts"] == SEVEN
    pinned = out["routes"]["zenmux"]["deepseek/deepseek-v4.1-flash:deepseek"]
    assert pinned["source"] == "provider"
    # The unpinned twin (other upstreams may serve it) is left alone.
    assert out["routes"]["zenmux"]["deepseek/deepseek-v4.1-flash"]["source"] == "measured"


@pytest.mark.parametrize("provider_id", ["no-effort-block", "not-listed"])
def test_missing_metadata_is_no_evidence_not_no_levels(declared_only, provider_id):
    before = _measured()
    snap = {"routes": {"deepseek": {"x": dict(before)}}}
    out = declared_only.merge_provider(
        snap, DEEPSEEK_MODELS, {("deepseek", "x"): provider_id}, "2026-09-30")
    assert out["routes"]["deepseek"]["x"] == before


def test_a_later_probe_never_widens_a_provider_ladder(refresh):
    """Acceptance is weaker evidence: re-probing DeepSeek would otherwise restore
    the parser's seven names, including the `medium`/`xhigh` aliases."""
    snap = {"routes": {"deepseek": {"deepseek-v4-flash": {
        "reasoning": True, "efforts": ["low", "high", "max"], "toggle": False,
        "source": "provider"}}}}
    probe = [{"model": "deepseek-v4-flash", "level": lv, "outcome": "accepted"}
             for lv in SEVEN]
    out = refresh.merge_probe(snap, probe, "deepseek", "2026-10-01")
    entry = out["routes"]["deepseek"]["deepseek-v4-flash"]
    assert entry["efforts"] == ["low", "high", "max"]
    assert entry["source"] == "provider"


def test_every_mapped_route_names_a_provider_channel(refresh):
    """A route-map key must be a real (channel, key) pair on a channel we refresh."""
    for provider, routes in refresh.PROVIDER_ROUTES.items():
        assert provider in refresh.CHANNEL_TO_PROVIDER
        for channel, key in routes:
            assert channel in refresh.CHANNEL_TO_PROVIDER, (channel, key)
            if channel == "zenmux":
                # Only a PINNED ZenMux route is known to be served by the vendor.
                assert key.endswith(f":{provider}"), key


# ---------------------------------------------------------------------------
# provider_ladder — the policy
# ---------------------------------------------------------------------------


def test_the_declared_ladder_is_kept_in_canonical_order(refresh):
    assert refresh.provider_ladder(["max", "low", "high"], {}) == ["low", "high", "max"]


def test_a_measured_none_survives_as_the_off_switch(refresh):
    """DeepSeek declares low/high/max, but a probe showed `none` disables thinking —
    a real setting, unlike the `medium`/`xhigh` aliases, which are dropped."""
    got = refresh.provider_ladder(["low", "high", "max"], _measured())
    assert got == ["none", "low", "high", "max"]


def test_none_needs_measured_evidence(refresh):
    unmeasured = {"efforts": SEVEN, "source": "models.dev"}
    assert refresh.provider_ladder(["low", "high"], unmeasured) == ["low", "high"]
    assert refresh.provider_ladder(["low", "high"], _measured(["low", "high"])) == [
        "low", "high"]


def test_a_level_outside_the_desk_vocabulary_is_dropped(refresh):
    assert refresh.provider_ladder(["low", "ultra", "max"], {}) == ["low", "max"]
