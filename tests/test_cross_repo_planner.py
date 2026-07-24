from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


cross_repo_plan = load_module("cross_repo_plan", ROOT / "skills/core/cross-repo-planner/scripts/cross_repo_plan.py")
delivery_plan = load_module("delivery_plan_templates", ROOT / "skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py")


def test_cross_repo_planner_example_generates_ready_graph() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        spec, registry, delivery = cross_repo_plan.example_inputs()
        graph, readiness, release = cross_repo_plan.render("REQ-X", spec, registry, delivery)
        cross_repo_plan.write_outputs(out, graph, readiness, release)
        assert graph["schema"] == "codex-cross-repo-execution-graph-v1"
        assert graph["decision"] == "ready"
        assert len(graph["repositories"]) == 3
        assert any(edge["from"] == "provider" and edge["to"] == "frontend" for edge in graph["dependency_edges"])
        assert graph["parallel_groups"]
        assert graph["contract_freeze_points"]
        assert readiness["decision"] == "ready"
        assert release["release_order"]
        validation = cross_repo_plan.validate_graph(json.loads((out / "cross_repo_execution_graph.json").read_text(encoding="utf-8")))
        assert validation["decision"] == "pass"


def test_cross_repo_planner_skips_single_repo_graph() -> None:
    graph, readiness, release = cross_repo_plan.render(
        "REQ-SINGLE",
        {"doc_id": "REQ-SINGLE", "summary": "single repo change"},
        {"app": {"name": "app", "dependencies": []}},
        {"repo_tasks": [{"repo": "app", "role": "modify", "tasks": ["edit"]}]},
    )
    assert graph["decision"] == "ready"
    assert graph["applicable"] is False
    assert readiness["decision"] == "pass"
    assert readiness["applicable"] is False
    assert release["decision"] == "pass"
    assert release["applicable"] is False
    assert cross_repo_plan.validate_graph(graph)["decision"] == "pass"


def test_cross_repo_planner_blocks_dependency_cycles() -> None:
    graph, readiness, release = cross_repo_plan.render(
        "REQ-CYCLE",
        {"doc_id": "REQ-CYCLE", "summary": "coordinated api contract change"},
        {
            "provider": {"name": "provider", "dependencies": ["consumer"]},
            "consumer": {"name": "consumer", "dependencies": ["provider"]},
        },
        {
            "repo_tasks": [
                {"repo": "provider", "role": "modify", "tasks": ["change api"]},
                {"repo": "consumer", "role": "modify", "tasks": ["consume api"]},
            ]
        },
    )
    assert graph["decision"] == "blocked"
    assert readiness["decision"] == "blocked"
    assert release["decision"] == "blocked"
    assert any(item["source"] == "dependency_edges" for item in graph["blockers"])
    assert cross_repo_plan.validate_graph(graph)["decision"] == "block"


def test_cross_repo_planner_blocks_unknown_registry_repos() -> None:
    graph, readiness, _release = cross_repo_plan.render(
        "REQ-UNKNOWN",
        {"doc_id": "REQ-UNKNOWN", "repositories": ["provider", "consumer"]},
        {"provider": {"name": "provider", "dependencies": []}},
        {"repo_tasks": [{"repo": "provider", "role": "modify", "tasks": ["edit"]}, {"repo": "consumer", "role": "modify", "tasks": ["edit"]}]},
    )
    assert graph["decision"] == "blocked"
    assert readiness["decision"] == "blocked"
    assert any(item["source"] == "consumer" for item in graph["blockers"])


def test_cross_repo_planner_readiness_blocks_missing_repo_tasks() -> None:
    graph, readiness, release = cross_repo_plan.render(
        "REQ-MISSING-TASKS",
        {"doc_id": "REQ-MISSING-TASKS", "repositories": ["provider", "consumer"]},
        {"provider": {"name": "provider", "dependencies": []}, "consumer": {"name": "consumer", "dependencies": ["provider"]}},
        {},
    )
    assert graph["decision"] == "ready"
    assert readiness["decision"] == "blocked"
    assert release["decision"] == "ready"
    assert {item["source"] for item in readiness["blockers"]} == {"provider", "consumer"}


def test_delivery_plan_template_emits_cross_repo_fields() -> None:
    plan = delivery_plan.example_plan("REQ-CROSS")
    assert isinstance(plan["parallel_groups"], list)
    assert isinstance(plan["dependency_edges"], list)
    assert isinstance(plan["integration_gates"], list)
    assert isinstance(plan["contract_freeze_points"], list)
    valid, issues = delivery_plan.validate(plan)
    assert valid, issues


def test_delivery_plan_template_validates_cross_repo_semantics() -> None:
    plan = delivery_plan.example_plan("REQ-CROSS")
    plan["dependency_edges"] = [{"from": "missing-provider", "to": "web-app", "type": "module_dependency"}]
    valid, issues = delivery_plan.validate(plan)
    assert not valid
    assert any("dependency_edges[0]" in issue for issue in issues)

    plan = delivery_plan.example_plan("REQ-CROSS")
    plan["repo_tasks"][1]["role"] = "modify"
    plan["repo_tasks"][1]["repo_path"] = "/workspace/pricing-service"
    plan["repo_tasks"][1]["allowed_files"] = ["src/pricing/api.py"]
    plan["parallel_groups"] = [{"group": 1, "repos": ["web-app", "pricing-service"], "mode": "parallel_safe"}]
    valid, issues = delivery_plan.validate(plan)
    assert not valid
    assert any("multiple modify repositories" in issue for issue in issues)


def test_codex_cli_cross_repo_plan_passthrough() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [
                "python3",
                "scripts/codex_eng.py",
                "run",
                "cross-repo-plan",
                "plan",
                "--example",
                "--out-dir",
                tmp,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["schema"] == "codex-cross-repo-planner-run-v1"
        assert data["decision"] == "ready"
        assert (Path(tmp) / "cross_repo_execution_graph.json").exists()


def test_codex_cli_cross_repo_validate_fails_for_invalid_graph() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        graph = Path(tmp) / "graph.json"
        graph.write_text(json.dumps({"schema": "wrong", "repositories": []}), encoding="utf-8")
        proc = subprocess.run(
            [
                "python3",
                "scripts/codex_eng.py",
                "run",
                "cross-repo-plan",
                "validate",
                "--graph",
                str(graph),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 1
        data = json.loads(proc.stdout)
        assert data["decision"] == "block"
