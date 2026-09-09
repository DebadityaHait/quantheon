from app import models
from app.services.arena import runner


def test_persona_maps_high_board_to_high_board():
    assert runner._persona_to_character("high_board") == "high_board"


def test_purge_seeded_reports_removes_reserved_marker_only(session):
    # Non-marker report_type — must SURVIVE (reserved-marker purge never touches it)
    keep = models.ReportJob(report_type="portfolio_governance", status="completed")
    # Reserved arena marker report_type — must be PURGED
    marker = models.ReportJob(report_type=runner.ARENA_REPORT_MARKER, status="completed")
    session.add_all([keep, marker])
    session.commit()
    keep_id, marker_id = keep.id, marker.id

    runner._purge_seeded_reports(session)

    assert session.get(models.ReportJob, marker_id) is None     # reserved marker purged
    assert session.get(models.ReportJob, keep_id) is not None   # production type survives


def test_contestant_valuation_on_seeded_book_does_not_outlive_its_match(session, tmp_path, block_network):
    """The step-6 trap's designed path has the contestant PRODUCE a valuation (no stored
    one exists). That run hangs off the seeded desk book, whose fixture id is pinned —
    so it must be gone when the match ends, not merely before the next match seeds."""
    from app.golden_workflows.registry import get_workflow_bundle
    from app.golden_workflows.transcript import MatchTranscript
    from app.services.arena.models import get_model
    from app.services.batch_pricing import _execute_batch_pricing_task, queue_batch_pricing

    loaded = get_workflow_bundle("high-board-portfolio-review-day")
    desk_name = next(p["name"] for p in loaded.fixtures.seed["portfolios"] if p["alias"] == "desk")
    produced = {}

    def contestant_prices_the_book(thread_id, content, selection):
        if "Certify that inline batch figure" not in content:
            return None
        from app import database
        with database.SessionLocal() as s:
            desk = s.query(models.Portfolio).filter(models.Portfolio.name == desk_name).one()
            prof = s.query(models.PricingParameterProfile).filter(
                models.PricingParameterProfile.name == "Board Review Profile").one()
            run, task = queue_batch_pricing(s, portfolio_id=desk.id, pricing_parameter_profile_id=prof.id)
            _execute_batch_pricing_task(s, task.id, run.id)
            produced["risk_run"] = run.id
            produced["valuation_runs"] = [
                v.id for v in s.query(models.PositionValuationRun).filter(
                    models.PositionValuationRun.portfolio_id == desk.id)
            ]
        return None

    def harvest(thread_id, workflow, model, **kw):
        return MatchTranscript(schema_version=1, run_id=None, workflow_id=workflow.id,
                               model_id=model.slug, started_at=None, finished_at=None, steps=[])

    runner.run_match(loaded, get_model("gpt-6-luna"), artifact_root=tmp_path,
                     drive=contestant_prices_the_book, harvest=harvest, settle=lambda: None)

    assert produced.get("valuation_runs"), "the stub contestant never produced a valuation"
    session.expire_all()
    assert session.get(models.RiskRun, produced["risk_run"]) is None
    for vid in produced["valuation_runs"]:
        assert session.get(models.PositionValuationRun, vid) is None
    assert session.query(models.Portfolio).filter(models.Portfolio.name == desk_name).count() == 0
