"""`scripts/arena_cost_report.py --billed` finds the ZenMux management key.

The repo's `.env` / `.env.example` spell it ZENMUX_MANAGEMENT_KEY, but the script used to
read only ZENMUX_MGT_KEY, so a configured key was never found and callers exported it
by hand. It also read only the process environment, and this desk's shell exports
EMPTY ZENMUX_* variables that shadow `.env` (an empty string is "set" to a naive
`os.environ.get`), which is the same trap that once made a configured API key read as a
403.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "arena_cost_report.py"
NAMES = ("ZENMUX_MANAGEMENT_KEY", "ZENMUX_MGT_KEY")


@pytest.fixture()
def report(monkeypatch):
    spec = importlib.util.spec_from_file_location("arena_cost_report_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPEN_OTC_ENV_FILE", "")  # no dotenv unless a test supplies one
    return module


def test_canonical_name_is_found(report, monkeypatch):
    monkeypatch.setenv("ZENMUX_MANAGEMENT_KEY", "mgmt-key")
    assert report._management_key() == "mgmt-key"


def test_canonical_name_wins_over_the_legacy_name(report, monkeypatch):
    monkeypatch.setenv("ZENMUX_MANAGEMENT_KEY", "new")
    monkeypatch.setenv("ZENMUX_MGT_KEY", "old")
    assert report._management_key() == "new"


def test_legacy_name_still_works(report, monkeypatch):
    monkeypatch.setenv("ZENMUX_MGT_KEY", "old")
    assert report._management_key() == "old"


def test_an_empty_ambient_value_is_unset_and_falls_back_to_dotenv(report, monkeypatch, tmp_path):
    dotenv = tmp_path / "fixture.env"
    dotenv.write_text('ZENMUX_MANAGEMENT_KEY="from-dotenv"\n')
    monkeypatch.setenv("OPEN_OTC_ENV_FILE", str(dotenv))
    monkeypatch.setenv("ZENMUX_MANAGEMENT_KEY", "")  # what the shell exports
    monkeypatch.setenv("ZENMUX_MGT_KEY", "   ")
    assert report._management_key() == "from-dotenv"


def test_a_real_environment_value_beats_dotenv(report, monkeypatch, tmp_path):
    dotenv = tmp_path / "fixture.env"
    dotenv.write_text('ZENMUX_MANAGEMENT_KEY="from-dotenv"\n')
    monkeypatch.setenv("OPEN_OTC_ENV_FILE", str(dotenv))
    monkeypatch.setenv("ZENMUX_MANAGEMENT_KEY", "from-env")
    assert report._management_key() == "from-env"


def test_no_key_anywhere_is_none_not_an_empty_string(report):
    assert report._management_key() is None
