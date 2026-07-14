from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


environment = load_module("environment_promotion", ROOT / "skills/core/environment-promotion-governor/scripts/environment_promotion.py")
uat = load_module("uat_acceptance", ROOT / "skills/core/uat-acceptance-governor/scripts/uat_acceptance.py")
release_change = load_module("release_change", ROOT / "skills/core/release-change-governor/scripts/release_change.py")
post_release = load_module("post_release_observer", ROOT / "skills/core/post-release-observer/scripts/post_release_observer.py")


def test_environment_template_blocks_until_evidence_filled() -> None:
    data = environment.template()
    result = environment.validate(data)
    assert result["decision"] == "block"
    assert result["blockers"]


def test_environment_passes_complete_evidence() -> None:
    data = environment.template()
    for item in data["environments"]:
        item["entry_criteria"] = ["previous env passed"]
        item["exit_criteria"] = ["smoke passed"]
        item["validation_evidence"] = ["test evidence"]
        item["rollback_ready"] = True
        item["approver"] = "owner"
        item["status"] = "passed"
    result = environment.validate(data)
    assert result["decision"] == "pass"


def test_uat_requires_signoff_and_cases() -> None:
    data = uat.template()
    assert uat.validate(data)["decision"] == "block"
    data.update({
        "scope": ["order export"],
        "acceptors": ["product owner"],
        "cases": [{"name": "admin export", "status": "passed"}],
        "signoff": {"accepted": True, "by": "product owner", "at": "2026-01-01", "notes": ""},
    })
    assert uat.validate(data)["decision"] == "pass"


def test_release_change_requires_window_and_rollback() -> None:
    data = release_change.template()
    assert release_change.validate(data)["decision"] == "block"
    data.update({
        "change_ticket": "CHG-1",
        "risk_level": "medium",
        "release_window": {"start": "10:00", "end": "11:00", "timezone": "UTC"},
        "approvers": ["owner"],
        "release_order": ["api-service"],
        "rollback_plan": ["redeploy previous version"],
        "rollback_owner": "owner",
        "post_release_checks": ["check error rate"],
    })
    assert release_change.validate(data)["decision"] == "pass"


def test_post_release_requires_observation_and_close() -> None:
    data = post_release.template()
    assert post_release.validate(data)["decision"] == "block"
    data.update({
        "observation_window": {"start": "10:00", "end": "10:30", "duration_minutes": 30},
        "metrics": [{"name": "error_rate", "status": "normal"}],
        "close": True,
        "closed_by": "owner",
    })
    assert post_release.validate(data)["decision"] == "pass"
    data.pop("incidents", None)
    assert post_release.validate(data)["decision"] == "pass"


def test_regulated_post_release_requires_provider_bound_audit_evidence() -> None:
    data = {
        "schema": "codex-post-release-observation-v1",
        "observation_window": {"start": "10:00", "end": "10:30", "duration_minutes": 30},
        "metrics": [{"provider": "metrics", "evidence_id": "MET-1", "observed_at": "10:30", "status": "healthy"}],
        "logs_checked": [{"provider": "logs", "evidence_id": "LOG-1", "observed_at": "10:30", "status": "healthy"}],
        "alerts_checked": [{"provider": "alerts", "evidence_id": "ALT-1", "observed_at": "10:30", "status": "healthy"}],
        "business_checks": [{"provider": "analytics", "evidence_id": "BIZ-1", "observed_at": "10:30", "status": "pass"}],
        "incidents": [{"id": "INC-1", "status": "resolved"}],
        "close": True,
        "closed_by": "release-owner",
        "closed_at": "2026-07-14T10:31:00+08:00",
        "close_evidence_id": "CLOSE-1",
    }

    assert post_release.validate(data, regulated=True)["decision"] == "pass"
    data["metrics"][0]["status"] = "degraded"
    assert post_release.validate(data, regulated=True)["decision"] == "block"


def run_all() -> None:
    test_environment_template_blocks_until_evidence_filled()
    test_environment_passes_complete_evidence()
    test_uat_requires_signoff_and_cases()
    test_release_change_requires_window_and_rollback()
    test_post_release_requires_observation_and_close()


if __name__ == "__main__":
    run_all()
    print("PASS release_governors tests")
