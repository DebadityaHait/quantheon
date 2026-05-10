"""Validate fixing evidence independently of native constructor kwargs."""
from __future__ import annotations

import json
import math
from typing import Any


def _stable_build_provenance(provenance: Any) -> dict[str, Any] | None:
    """Fields that identify the build, excluding mutable validation-market context."""
    if not isinstance(provenance, dict):
        return None
    representation = provenance.get("representation")
    supplied_inputs = provenance.get("supplied_inputs")
    fixing_references = provenance.get("fixing_references", [])
    if (representation not in ("raw_build_inputs", "native_product_terms")
            or not isinstance(supplied_inputs, dict)
            or not isinstance(fixing_references, list)):
        return None
    return {"representation": representation,
            "supplied_inputs": supplied_inputs,
            "fixing_references": fixing_references}


def resolve_fixing_references(references: list[dict], *, config, underlying: str,
                              initial_price: Any) -> list[dict]:
    from app import database
    from app.services.deep_agent.artifact_access import workflow_id_from_config, get_workflow_artifact, raw_artifact_content
    workflow = workflow_id_from_config(config)
    resolved = []
    with database.SessionLocal() as session:
        for ref in references:
            artifact = get_workflow_artifact(session, workflow_id=workflow, artifact_id=ref["artifact_id"])
            if artifact.tool_name != "fetch_market_snapshot" or artifact.kind != "tool_result":
                raise ValueError("Fixing reference must identify a captured market snapshot")
            snapshot = json.loads(raw_artifact_content(artifact))
            if snapshot.get("symbol") != underlying or snapshot.get("source_metadata", {}).get("fallback"):
                raise ValueError("Fixing snapshot underlying mismatch or fallback")
            rows = (snapshot.get("data") or {}).get("rows") or []
            rows = [row for row in rows if str(row.get("date")) == ref["fixing_date"]]
            if len(rows) != 1 or initial_price is None or not math.isclose(float(rows[0]["close"]), float(initial_price), rel_tol=0, abs_tol=1e-8):
                raise ValueError("Fixing date/close does not match the supplied initial price")
            resolved.append({"kind": "artifact", "artifact_id": artifact.id,
                             "content_hash": artifact.payload["content_hash"],
                             "fixing_date": ref["fixing_date"], "symbol": underlying,
                             "role": "initial_fixing", "json_pointer": "/data/rows",
                             "retrieve": "read_artifact(artifact_id, json_pointer='/data/rows')"})
    return resolved


def validate_source_payload(source: dict, *, config, underlying: str,
                            terms: dict | None = None, family: str | None = None) -> dict:
    """Reverify copied provenance at persistence; a model payload grants no trust."""
    if set(source) - {"build_provenance"}:
        raise ValueError("Product source_payload accepts only captured build_provenance, not attribution controls")
    provenance = source.get("build_provenance")
    if provenance:
        from app import database
        from app.models import SessionArtifact
        from app.services.deep_agent.artifact_access import workflow_id_from_config, raw_artifact_content
        workflow = workflow_id_from_config(config)
        captured_provenance = None
        with database.SessionLocal() as session:
            for artifact in session.query(SessionArtifact).filter_by(workflow_id=workflow, kind="tool_result", tool_name="build_product"):
                result = json.loads(raw_artifact_content(artifact))
                spec = result.get("product_spec") or {}
                candidate_provenance = (spec.get("source_payload") or {}).get("build_provenance")
                if (result.get("ok") and spec.get("underlying") == underlying
                    and (family is None or spec.get("quantark_class") == family)
                    and (terms is None or spec.get("terms") == terms)
                    and _stable_build_provenance(candidate_provenance) is not None
                    and _stable_build_provenance(candidate_provenance) == _stable_build_provenance(provenance)):
                    captured_provenance = candidate_provenance
                    break
        if captured_provenance is None:
            raise ValueError("Build provenance does not match a captured product build in the current workflow")
        # Persistence always receives the server-captured source. Callers may
        # carry harmlessly changed validation-market context, but cannot replace
        # the build inputs or fixing dependencies.
        provenance = json.loads(json.dumps(captured_provenance))
    else:
        return source
    refs = provenance.get("fixing_references") or []
    if refs:
        provenance["fixing_references"] = resolve_fixing_references(
            refs, config=config, underlying=underlying,
            initial_price=(provenance.get("supplied_inputs") or {}).get("initial_price"))
    return {**source, "build_provenance": provenance}
