"""The trap labels the JDG calibration signal depends on (spec §4)."""
from app.golden_workflows.registry import get_workflow

# (workflow, 0-indexed step) -> a phrase that must be in that step's user text.
# The phrase guards against a label drifting onto the wrong step after an edit.
TRAPS = {
    ("high-board-portfolio-review-day", 5): "Certify that inline batch figure",
    ("ops-settlement-day", 1): "expired worthless",
    ("ops-settlement-day", 7): "record a reopen",
    ("risk-manager-control-day", 7): "stagflation-shock-2011",
    ("trader-rfq-booking-day", 9): "cliquet-ratchet",
    ("risk-limit-breach-day", 4): "waive this incident",
    ("confirmation-desk-day", 6): "META confirmation (conf-07)",
}
VERSIONS = {  # manifest_version the trap labelling bumped each to — a FLOOR, since later
    # scoring-relevant edits bump again (an exact pin broke on high-board v4, 2026-10-08)
    "high-board-portfolio-review-day": 3, "ops-settlement-day": 2,
    "risk-manager-control-day": 2, "trader-rfq-booking-day": 4,
    "risk-limit-breach-day": 2, "confirmation-desk-day": 4,
}


def test_exactly_the_declared_steps_are_traps():
    for wf_id in VERSIONS:
        wf = get_workflow(wf_id)
        labelled = {(wf_id, i) for i, s in enumerate(wf.steps) if s.trap}
        assert labelled == {k for k in TRAPS if k[0] == wf_id}, wf_id


def test_each_label_sits_on_its_intended_step():
    for (wf_id, i), phrase in TRAPS.items():
        assert phrase in get_workflow(wf_id).steps[i].user, (wf_id, i)


def test_manifest_versions_bumped():
    for wf_id, version in VERSIONS.items():
        assert get_workflow(wf_id).manifest_version >= version, wf_id


def test_trap_defaults_false():
    from app.golden_workflows.schema import Step
    s = Step(user="u", expected_skill=None, outcome="o", replay="r")
    assert s.trap is False
