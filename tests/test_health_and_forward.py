from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

B_LEVEL_UPGRADE_SKILLS = [
    "skills/core/api-surface-extractor/SKILL.md",
    "skills/core/baseline-quality-governor/SKILL.md",
    "skills/core/change-risk-governor/SKILL.md",
    "skills/core/code-index-builder/SKILL.md",
    "skills/core/code-index-lookup/SKILL.md",
    "skills/core/config-surface-extractor/SKILL.md",
    "skills/core/dependency-surface-analyzer/SKILL.md",
    "skills/core/diff-impact-analyzer/SKILL.md",
    "skills/core/evidence-auto-collector/SKILL.md",
    "skills/core/git-history-miner/SKILL.md",
    "skills/core/human-doc-reviewer/SKILL.md",
    "skills/templates/ci-templates/SKILL.md",
]

FINAL_A_LEVEL_SKILLS = [
    "skills/core/artifact-schema-governor/SKILL.md",
    "skills/core/dependency-license-governor/SKILL.md",
    "skills/core/deprecation-governor/SKILL.md",
    "skills/core/issue-pr-governor/SKILL.md",
    "skills/core/post-release-observer/SKILL.md",
    "skills/core/prompt-pack-governor/SKILL.md",
    "skills/core/requirement-document-ingestor/SKILL.md",
    "skills/core/skill-installation-governor/SKILL.md",
]


def score_skill_doc(text: str, script_count: int, schema_count: int, test_refs: int) -> int:
    words = len(re.findall(r"\w+", text))
    score = 50
    score += min(15, script_count * 8)
    score += min(12, schema_count * 3)
    score += 8 if "## Rules" in text else 0
    score += 8 if "## Output" in text else 0
    score += 5 if "## Position" in text else 0
    score += min(10, test_refs * 5)
    score += 5 if "```bash" in text else 0
    score += 5 if words >= 180 else 0
    return min(score, 100)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


skill_health = load_module("skill_health", ROOT / "skills/core/skill-health/scripts/skill_health.py")
overlay_health = load_module("overlay_health", ROOT / "skills/core/overlay-health/scripts/overlay_health.py")
human_doc_review = load_module("human_doc_review", ROOT / "skills/core/human-doc-reviewer/scripts/human_doc_review.py")
forward_test = load_module("forward_test", ROOT / "skills/core/forward-test-runner/scripts/forward_test.py")
scenario_catalog = load_module("scenario_catalog", ROOT / "scripts/scenario_catalog.py")
benchmark = load_module("benchmark", ROOT / "skills/core/benchmark-governor/scripts/benchmark.py")
implement_dry_run = load_module("implement_dry_run", ROOT / "scripts/implement_dry_run.py")


def test_skill_health_runs_on_repo() -> None:
    result = skill_health.check(ROOT)
    assert result["schema"] == "codex-skill-health-v1"
    assert result["decision"] in {"pass", "warn"}
    assert result["skill_count"] > 10
    assert result["advanced_or_better_count"] > 0
    assert result["expert_readiness"] in {"expert", "advanced", "mixed"}
    assert result["framework_expert_assessment"]["dimensions"]["dag_integrity"] == 100
    assert result["framework_expert_assessment"]["dimensions"]["gate_semantics"] == 100
    assert result["framework_expert_assessment"]["dimensions"]["happy_blocked_path_reality"] == 100
    assert result["framework_expert_assessment"]["level"] == "advanced"
    assert len(result["skill_scores"]) == result["skill_count"]
    assert {"skill", "score", "level", "dimensions"}.issubset(result["skill_scores"][0])
    assert "content_quality" in result["skill_scores"][0]
    assert result["content_quality_average"] > 0
    assert result["content_quality_expert_count"] > 0
    assert result["integrated_quality_gates"]["design_template_regression"]["decision"] == "pass"
    example_names = {item["name"] for item in result["integrated_quality_gates"]["design_template_regression"]["examples"]}
    assert "new_service_design_example" in example_names
    assert not [item for item in result["warnings"] if item["message"] == "skill is not listed in README"]


def test_root_skill_health_wrapper_exists_for_readme_command() -> None:
    wrapper = ROOT / "scripts/skill_health.py"
    assert wrapper.exists()
    assert "skills/core/skill-health/scripts/skill_health.py" in wrapper.read_text(encoding="utf-8")


def test_skill_health_counts_only_validated_real_project_replays() -> None:
    calibration = skill_health.real_project_calibration(ROOT)
    assert calibration["validation_decision"] == "pass"
    assert calibration["count"] == 0
    assert calibration["families"] == []
    assert calibration["agreement_rate"] == 0


def test_behavior_test_signals_resolves_module_level_skill_aliases() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tests = root / "tests"
        tests.mkdir()
        (tests / "test_example.py").write_text(
            "from pathlib import Path\n\n"
            "ROOT = Path(__file__).parent\n"
            "SCRIPT = ROOT / 'skills/core/example-governor/scripts/check.py'\n"
            "spec = make_spec(SCRIPT)\n"
            "example = load_from_spec(spec)\n"
            "other = load_module('unrelated')\n\n"
            "def test_example_allows_valid_input():\n"
            "    assert example.check({'valid': True})\n\n"
            "def test_example_rejects_missing_input():\n"
            "    assert not example.check({})\n\n"
            "def test_unrelated_behavior():\n"
            "    assert other.check()\n",
            encoding="utf-8",
        )
        assert skill_health.behavior_test_signals(root, "example-governor") == (2, 1)


def test_behavior_test_signals_does_not_count_unused_skill_import() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        tests = root / "tests"
        tests.mkdir()
        (tests / "test_example.py").write_text(
            "example = load_module('skills/core/example-governor/scripts/check.py')\n\n"
            "def test_unrelated_rejects_missing_input():\n"
            "    assert unrelated.check({})\n",
            encoding="utf-8",
        )
        assert skill_health.behavior_test_signals(root, "example-governor") == (0, 0)


def test_all_skill_docs_declare_output_section() -> None:
    offenders = []
    for path in sorted((ROOT / "skills").glob("*/*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        if not re.search(r"^## Output$", text, flags=re.MULTILINE):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders


def test_all_skill_docs_declare_taxonomy_frontmatter() -> None:
    offenders = []
    required = {"category", "maturity", "stage", "gate"}
    for path in sorted((ROOT / "skills").glob("*/*/SKILL.md")):
        fm = skill_health.parse_frontmatter(path.read_text(encoding="utf-8"))
        missing = sorted(required - set(fm))
        if missing:
            offenders.append({"path": path.relative_to(ROOT).as_posix(), "missing": missing})
    assert not offenders


def test_skill_health_blocks_invalid_expert_gate_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        skill = root / "skills/core/bad-gate/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            "---\n"
            "name: bad-gate\n"
            "description: Bad gate.\n"
            "category: template-runner\n"
            "maturity: expert-gate\n"
            "stage: design\n"
            "gate: false\n"
            "---\n"
            "# Bad Gate\n\n## Output\nschema decision blockers\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text("bad-gate\n", encoding="utf-8")
        docs = root / "docs"
        docs.mkdir()
        (docs / "open-source-roadmap.md").write_text("`done`\n", encoding="utf-8")
        tests = root / "tests"
        tests.mkdir()
        (tests / "test_bad_gate.py").write_text("bad_gate\n", encoding="utf-8")
        result = skill_health.check(root)
        assert result["decision"] == "block"
        messages = " ".join(item["message"] for item in result["blockers"])
        assert "expert-gate skills must declare gate=true" in messages
        assert "template and extractor skills must not be marked expert-gate" in messages


def test_workflow_profiles_reference_existing_skills() -> None:
    profiles = skill_health.load_restricted_yaml(ROOT / "config/workflow-profiles.example.yaml")
    assert profiles["schema"] == "codex-workflow-profiles-v3"
    skill_names = {
        skill_health.parse_frontmatter(path.read_text(encoding="utf-8"))["name"]
        for path in (ROOT / "skills").glob("*/*/SKILL.md")
    }
    profile_names = {item["name"] for item in profiles["profiles"]}
    assert {"bugfix", "small_feature", "frontend_change", "cross_repo_api", "data_migration", "release_readiness"}.issubset(profile_names)
    for profile in profiles["profiles"]:
        required = profile.get("required_skills", [])
        assert required
        assert set(profile.get("cost_budget", {})) == {
            "max_executed_steps",
            "max_generated_artifacts",
            "max_command_duration_ms",
        }
        assert all(value > 0 for value in profile["cost_budget"].values())
        assert all(item in skill_names for item in required)
        assert profile.get("required_gate_artifacts")
        gate_artifacts = {item["artifact"] for item in profile["required_gate_artifacts"]}
        assert gate_artifacts.issubset(set(profile.get("expected_artifacts", [])))
        if profile["name"] != "release_readiness":
            expected = set(profile.get("expected_artifacts", []))
            assert {"test_design.json", "docs_quality.json"}.issubset(expected)
            assert {"test_design.json", "docs_quality.json"}.issubset(gate_artifacts)
    frontend = next(item for item in profiles["profiles"] if item["name"] == "frontend_change")
    assert "frontend-implementation-planner" in frontend["required_skills"]
    assert "frontend-acceptance-runner" not in frontend["required_skills"]
    assert "test-evidence-gate" not in frontend["required_skills"]
    release = next(item for item in profiles["profiles"] if item["name"] == "release_readiness")
    assert "release-evidence-binder" in release["required_skills"]
    stages = skill_health.load_restricted_yaml(ROOT / "config/workflow-stages.example.yaml")
    assert stages["schema"] == "codex-workflow-stages-v4"
    assert {"spec", "delivery_plan_review", "edit_permit", "release"}.issubset({item["name"] for item in stages["stages"]})


def test_workflow_profiles_follow_canonical_design_order() -> None:
    profiles = skill_health.load_restricted_yaml(ROOT / "config/workflow-profiles.example.yaml")["profiles"]
    assert all(len(profile["required_skills"]) == len(set(profile["required_skills"])) for profile in profiles)
    small = next(item for item in profiles if item["name"] == "small_feature")
    assert small["required_skills"].index("domain-model-governor") < small["required_skills"].index("architecture-framing-governor") < small["required_skills"].index("technical-design-governor")


def test_workflow_stage_registry_uses_pre_technical_design_order() -> None:
    stages = skill_health.load_restricted_yaml(ROOT / "config/workflow-stages.example.yaml")["stages"]
    names = [item["name"] for item in stages]
    expected = [
        "requirement_ingestion",
        "spec",
        "requirement_questions",
        "domain_model_design",
        "architecture_framing",
        "technical_design",
        "architecture_design",
        "configuration_design_review",
        "data_security_design_review",
        "performance_design_review",
        "cross_repo_plan",
        "test_design",
        "design_review",
        "test_data_plan",
        "delivery_plan",
        "initial_traceability",
        "delivery_plan_review",
        "post_change",
        "post_implementation_traceability",
    ]
    assert [name for name in names if name in expected] == expected
    assert all(item.get("phase") for item in stages)
    assert all(isinstance(item.get("depends_on"), list) for item in stages)
    artifacts = {item["artifact"] for item in stages}
    profiles = skill_health.load_restricted_yaml(ROOT / "config/workflow-profiles.example.yaml")["profiles"]
    assert all(gate["artifact"] in artifacts for profile in profiles for gate in profile["required_gate_artifacts"])


def test_workflow_docs_describe_current_order() -> None:
    workflow = (ROOT / "docs/workflow-guide.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    catalog = (ROOT / "docs/skill-catalog.md").read_text(encoding="utf-8")
    scenario = (ROOT / "docs/scenario-guide.md").read_text(encoding="utf-8")
    for text in [workflow, architecture, catalog, scenario]:
        assert "architecture-framing" in text or "architecture framing" in text
    assert workflow.index("domain-model-governor") < workflow.index("architecture-framing-governor") < workflow.index("technical-design-governor")
    assert workflow.index("frontend-acceptance-runner") < workflow.index("test-evidence-gate")


def test_readme_uses_current_validation_commands() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python3 -m pytest -q" in readme
    assert "python3 -m compileall -q scripts skills tests" in readme
    assert "python3 scripts/skill_health.py --root ." in readme


def test_docs_describe_full_pre_edit_gate() -> None:
    paths = [
        ROOT / "README.md",
        ROOT / "docs/getting-started.md",
        ROOT / "docs/workflow-guide.md",
        ROOT / "docs/scenario-guide.md",
    ]
    required = [
        "technical_design",
        "architecture_design",
        "design_architecture_review",
        "delivery_plan_review",
        "implementation_allowed=true",
        "pull --ff-only",
        "edit_permit",
        "write_guard_snapshot",
        "write_guard_audit",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        missing = [item for item in required if item not in text]
        assert not missing, f"{path.relative_to(ROOT)} missing {missing}"


def test_architecture_documents_skill_taxonomy_and_gate_contract() -> None:
    architecture = (ROOT / "docs/architecture.md").read_text(encoding="utf-8")
    assert "## Skill Taxonomy" in architecture
    assert "## Gate Contract" in architecture
    assert "`expert-gate`" in architecture
    assert "`schema`" in architecture
    assert "`decision`" in architecture
    assert "`blockers`" in architecture


def test_skill_catalog_lists_all_skills_with_maturity() -> None:
    catalog = (ROOT / "docs/skill-catalog.md").read_text(encoding="utf-8")
    for path in sorted((ROOT / "skills").glob("*/*/SKILL.md")):
        rel = path.parent.relative_to(ROOT).as_posix()
        fm = skill_health.parse_frontmatter(path.read_text(encoding="utf-8"))
        assert rel in catalog
        assert fm["maturity"] in catalog
        assert fm["category"] in catalog


def test_previously_b_level_skill_docs_have_operational_guidance() -> None:
    offenders = []
    required_sections = ["## Position", "## Rules", "## Output"]
    for rel in B_LEVEL_UPGRADE_SKILLS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        missing = [section for section in required_sections if section not in text]
        if missing or len(re.findall(r"^- ", text, flags=re.MULTILINE)) < 5:
            offenders.append({"path": rel, "missing": missing})
    assert not offenders


def test_final_target_skill_docs_have_operational_guidance() -> None:
    offenders = []
    required_sections = ["## Position", "## Rules", "## Output"]
    for rel in FINAL_A_LEVEL_SKILLS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        missing = [section for section in required_sections if section not in text]
        if missing or len(re.findall(r"^- ", text, flags=re.MULTILINE)) < 5:
            offenders.append({"path": rel, "missing": missing})
    assert not offenders


def test_skill_quality_distribution_is_all_a_level() -> None:
    tests_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_*.py"))
    levels: dict[str, list[str]] = {"A": [], "B+": [], "B": [], "C+": [], "C": []}
    for path in sorted((ROOT / "skills").glob("*/*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        script_text = "\n".join(
            script.read_text(encoding="utf-8", errors="ignore") for script in (path.parent / "scripts").glob("*.py")
        )
        schemas = set(re.findall(r"codex-[a-z0-9-]+-v\d+", text + "\n" + script_text))
        name = path.parent.name
        test_refs = sum(1 for pattern in [name, name.replace("-", "_")] if pattern in tests_text)
        score = score_skill_doc(text, len(list((path.parent / "scripts").glob("*.py"))), len(schemas), test_refs)
        level = "A" if score >= 90 else "B+" if score >= 82 else "B" if score >= 75 else "C+" if score >= 68 else "C"
        levels[level].append(path.relative_to(ROOT).as_posix())
    assert len(levels["A"]) == len(list((ROOT / "skills").glob("*/*/SKILL.md")))
    assert levels["B+"] == []
    assert levels["B"] == []
    assert levels["C+"] == []
    assert levels["C"] == []


def test_overlay_health_blocks_missing_registry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = overlay_health.check(Path(tmp))
        assert result["decision"] == "block"
        assert result["blockers"]


def test_overlay_health_blocks_missing_declared_assets_and_warns_stale_assets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "skills/web-app").mkdir(parents=True)
        (root / "skills/web-app/SKILL.md").write_text(
            "# Web App\n\nOwner boundary: frontend module.\nCommands: npm run build.\nTest command: npm test.\nCode-index: indexes/web-app.code_index.json.\n",
            encoding="utf-8",
        )
        (root / "projects.yaml").write_text(
            "projects:\n"
            "  - name: web-app\n"
            "    assets:\n"
            "      index: indexes/web-app.code_index.json\n"
            "      baseline: baseline/web-app.baseline.json\n",
            encoding="utf-8",
        )
        missing = overlay_health.check(root)
        assert missing["decision"] == "block"
        messages = " ".join(item["message"] for item in missing["blockers"])
        assert "project index missing" in messages
        assert "baseline docs missing" in messages

        (root / "indexes").mkdir()
        (root / "baseline").mkdir()
        old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
        (root / "indexes/web-app.code_index.json").write_text(json.dumps({"generated_at": old}), encoding="utf-8")
        (root / "baseline/web-app.baseline.json").write_text(json.dumps({"source_revision": "abc123"}), encoding="utf-8")
        stale = overlay_health.check(root, freshness_days=30)
        assert stale["decision"] == "warn"
        assert any("days old" in item["message"] for item in stale["warnings"])


def test_overlay_health_reviews_project_skill_guidance_quality() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "skills/web-app").mkdir(parents=True)
        (root / "skills/web-app/SKILL.md").write_text("---\nname: web-app\ndescription: x\n---\n# Web App\n", encoding="utf-8")
        (root / "projects.yaml").write_text(
            "projects:\n"
            "  - name: web-app\n"
            "    assets:\n"
            "      index: indexes/web-app.code_index.json\n"
            "      baseline: baseline/web-app.baseline.json\n",
            encoding="utf-8",
        )
        (root / "indexes").mkdir()
        (root / "baseline").mkdir()
        now = datetime.now(timezone.utc).isoformat()
        (root / "indexes/web-app.code_index.json").write_text(json.dumps({"generated_at": now}), encoding="utf-8")
        (root / "baseline/web-app.baseline.json").write_text(json.dumps({"generated_at": now}), encoding="utf-8")
        weak = overlay_health.check(root)
        assert weak["decision"] == "block"
        assert any("ownership and code index" in item["message"] for item in weak["blockers"])

        (root / "skills/web-app/SKILL.md").write_text(
            "# Web App\n\nOwner boundary: frontend module.\nCommands: npm run build.\nTest command: npm test.\nCode-index: indexes/web-app.code_index.json.\n",
            encoding="utf-8",
        )
        strong = overlay_health.check(root)
        assert strong["decision"] == "pass"


def test_overlay_health_policy_can_require_team_sections() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "skills/web-app").mkdir(parents=True)
        (root / "skills/web-app/SKILL.md").write_text(
            "# Web App\n\nOwner boundary: frontend module.\nCommands: npm run build.\nTest command: npm test.\nCode-index: indexes/web-app.code_index.json.\n",
            encoding="utf-8",
        )
        (root / "projects.yaml").write_text("projects:\n  - name: web-app\n", encoding="utf-8")
        (root / "indexes").mkdir()
        (root / "baseline").mkdir()
        now = datetime.now(timezone.utc).isoformat()
        (root / "indexes/web-app.code_index.json").write_text(json.dumps({"generated_at": now}), encoding="utf-8")
        (root / "baseline/web-app.baseline.json").write_text(json.dumps({"generated_at": now}), encoding="utf-8")
        policy = {
            "freshness_days": 14,
            "project_skill_required_sections": {
                "ownership": ["owner"],
                "release_boundary": ["release boundary"],
            },
            "block_on_missing_sections": ["release_boundary"],
        }
        result = overlay_health.check(root, policy=policy)
        assert result["decision"] == "block"
        assert any("release_boundary" in item["message"] for item in result["blockers"])


def test_overlay_health_supports_installed_company_layout_and_json_registry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry").mkdir()
        (root / "web-app").mkdir()
        (root / "web-app/SKILL.md").write_text(
            "# Web App\n\nOwner boundary: frontend module.\nCommands: npm run build.\nTest command: npm test.\nCode-index: indexes/web-app.code_index.json.\n",
            encoding="utf-8",
        )
        (root / "registry/projects.json").write_text(
            json.dumps({
                "schema": "company-project-registry-v1",
                "projects": [{
                    "name": "web-app",
                    "skill": "web-app",
                    "analysis": {
                        "codeIndex": "indexes/web-app.code_index.json",
                        "baseline": "baseline/web-app.baseline.json",
                    },
                }],
            }),
            encoding="utf-8",
        )
        (root / "indexes").mkdir()
        (root / "baseline").mkdir()
        now = datetime.now(timezone.utc).isoformat()
        metadata = {"generated_at": now, "source_revision": "abc123"}
        (root / "indexes/web-app.code_index.json").write_text(json.dumps(metadata), encoding="utf-8")
        (root / "baseline/web-app.baseline.json").write_text(json.dumps(metadata), encoding="utf-8")
        result = overlay_health.check(root)
        assert result["decision"] == "pass"
        assert result["registry_sources"] == ["registry/projects.json"]
        assert result["project_count"] == 1
        assert result["project_skill_count"] == 1
        assert len(result["checked_assets"]) == 2


def test_overlay_health_skips_declared_tool_skills() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "projects.yaml").write_text(
            "projects:\n"
            "  - name: project-tool\n"
            "    skill_type: tool\n",
            encoding="utf-8",
        )
        result = overlay_health.check(root)
        assert result["decision"] == "pass"
        assert result["project_count"] == 1
        assert result["project_skill_count"] == 0
        assert result["skipped_skill_count"] == 1
        assert result["checked_assets"] == []


def test_human_doc_review_detects_local_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        local_path = "/" + "Users/example/private"
        doc.write_text(f"Scope\nDecision\nOptions\nRisk\nEvidence\nRollback\n{local_path}\n", encoding="utf-8")
        result = human_doc_review.review(doc)
        assert result["decision"] == "block"
        assert any(item["source"] == "local_path" for item in result["blockers"])


def test_human_doc_review_warns_thin_doc() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        doc.write_text("short\n", encoding="utf-8")
        result = human_doc_review.review(doc)
        assert result["decision"] == "warn"
        assert result["warnings"]


def test_human_doc_review_strict_blocks_warnings() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        doc.write_text("short\n", encoding="utf-8")
        result = human_doc_review.review(doc, strict=True)
        assert result["decision"] == "block"
        assert result["blockers"]


def test_human_doc_review_strict_is_doc_type_aware_for_specs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "human/specs/REQ-1.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "# Order export Spec\n\n"
            "## Executive Summary\n\n"
            "Review focus: confirm the requirement boundary, acceptance coverage, and evidence links before design starts.\n\n"
            "## Background And Goals\n\n"
            "Background: operations needs a clear export requirement. Goal: define scope and acceptance criteria without committing to implementation options.\n\n"
            "## Scope\n\n"
            "The scope is exporting filtered order data for authorized users while preserving existing behavior outside the export flow.\n\n"
            "This scope explicitly excludes schema migration, release sequencing, rollback ownership, and design option selection because those belong to downstream design and release documents.\n\n"
            "## Requirement Clarification\n\n"
            "Clarification log: no open product questions remain. Confirmed understanding: export includes order id and status.\n\n"
            "The clarification outcome is specific enough for design because the actor, exported fields, and expected evidence are all named.\n\n"
            "## Acceptance Criteria\n\n"
            "- `AC-1` exported file contains order id and status.\n\n"
            "The acceptance criterion is intentionally narrow so the delivery plan can map it to functional and regression test cases without inventing extra product behavior.\n\n"
            "## Requirement Traceability Diagram\n\n"
            "Traceability links `AC-1` to downstream design, test, and release evidence.\n\n"
            "```mermaid\nflowchart LR\nREQ-->AC1\n```\n\n"
            "## Evidence References\n\n"
            "- `spec.json`\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc, strict=True)
        assert result["doc_type"] == "spec"
        assert result["decision"] != "block"
        blocked_sources = {item["source"] for item in result["blockers"]}
        assert "options" not in blocked_sources
        assert "rollback" not in blocked_sources


def test_human_doc_review_strict_requires_design_depth_for_designs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "human/designs/REQ-1.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "# Order export Design\n\n"
            "## Decision Records\n\n"
            "Decision: implement scoped export behavior.\n\n"
            "## Evidence References\n\n"
            "- `technical_design.json`\n\n"
            "```mermaid\nflowchart LR\nA-->B\n```\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc, strict=True)
        assert result["doc_type"] == "design"
        assert result["decision"] == "block"
        blocked_sources = {item["source"] for item in result["blockers"]}
        assert {"options", "risk", "rollback", "test", "traceability", "implementation_boundary"}.issubset(blocked_sources)
        assert "system_sequence_diagram" in blocked_sources


def test_human_doc_review_blocks_design_decision_before_options() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "human/designs/REQ-ORDER.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "# 订单导出 技术设计\n\n"
            "## 一、摘要\n\n"
            "范围 决策 方案 风险 证据 回滚 背景 目标 澄清 验收 测试 追踪 实施边界 评审重点。\n\n"
            "## 技术决策结论\n\n"
            "- 选中：`T1`\n\n"
            "## 技术候选方案详述\n\n"
            "### 方案 `T1`：单模块实现\n\n"
            "- 适用条件：单模块、低风险。\n"
            "- 风险：需要回归测试。\n\n"
            "## 风险与回滚\n\n"
            "风险可控，回滚到旧版本。\n\n"
            "## 追踪关系与证据\n\n"
            "- `technical_design.json`\n\n"
            "```mermaid\nflowchart LR\nA-->B\n```\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc)
        assert result["decision"] == "block"
        assert any(item["source"] == "decision_order" for item in result["blockers"])


def test_human_doc_review_accepts_brks_bound_to_unchanged_referenced_api() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "human/designs/REQ-FE.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "# Frontend Design\n\n"
            "## Candidate Options\n\n"
            "#### Option `R1`: frontend-only implementation\n\n"
            "## Decision\n\nSelect R1.\n\n"
            "## Sub-Requirement Design\n\n"
            "#### BRK-1 rebuild player subscription\n"
            "- API applicability: excluded; existing API paths, fields, and response shapes remain unchanged.\n"
            "- Referenced API: `/operate/api/dualCamera/playbackStreamControl`\n\n"
            "#### BRK-2 clean player resources\n"
            "- Uses the same unchanged contract above.\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc)
        assert not any(item["source"] == "brk_api_binding" for item in result["blockers"])


def test_human_doc_review_strict_is_doc_type_aware_for_tests() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "human/tests/REQ-1.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "# Order export Test Design\n\n"
            "## Acceptance Evidence Mapping\n\n"
            "- Acceptance AC-1 maps to `test_design.json` and `test_evidence_gate.json` evidence.\n\n"
            "## Test Strategy Summary\n\n"
            "- Test admin export, permission denial, regression scope, and frontend acceptance.\n\n"
            "## Test Cases\n\n"
            "- TC-1 verifies export output.\n"
            "- TC-PERM-1 verifies unauthorized users cannot export.\n\n"
            "## Traceability\n\n"
            "- Traceability links spec acceptance criteria to test cases and release evidence.\n\n"
            "## Evidence References\n\n"
            "- `test_design.json`\n"
            "- `test_evidence_gate.json`\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc, strict=True)
        assert result["doc_type"] == "test"
        assert result["decision"] != "block"
        blocked_sources = {item["source"] for item in result["blockers"]}
        assert "options" not in blocked_sources
        assert "rollback" not in blocked_sources
        assert "implementation_boundary" not in blocked_sources


def test_human_doc_review_blocks_chinese_test_doc_without_execution_details() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "human/tests/REQ-ORDER.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "# 订单导出 测试设计\n\n"
            "## 一、摘要\n\n"
            "范围 验收 测试 证据 追踪。\n\n"
            "## 二、验收证据映射\n\n"
            "- `AC-1` 映射到 `test_design.json`。\n\n"
            "## 三、测试策略摘要\n\n"
            "- 覆盖功能测试和回归测试。\n\n"
            "## 四、测试用例\n\n"
            "### `TC-1` 验证订单导出\n\n"
            "- 关联验收：`AC-1`\n"
            "- 执行步骤：打开页面，点击导出。\n"
            "- 预期结果：导出成功。\n\n"
            "## 八、追踪关系\n\n"
            "- 追踪到 `spec.json`。\n\n"
            "## 九、证据引用\n\n"
            "- `test_design.json`\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc)
        assert result["decision"] == "block"
        sources = {item["source"] for item in result["blockers"]}
        assert {"test_execution_path", "test_assertions", "test_data_setup"}.issubset(sources)


def test_human_doc_review_accepts_review_style_test_case_sections() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "human/tests/REQ-ORDER.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "# 订单导出 测试设计\n\n"
            "## 一、摘要\n\n"
            "范围 验收 测试 证据 追踪。\n\n"
            "## 二、验收证据映射\n\n"
            "- `AC-1` 映射到 `test_design.json`。\n\n"
            "## 三、测试策略摘要\n\n"
            "- 覆盖功能测试和回归测试。\n\n"
            "## 四、测试用例\n\n"
            "### `TC-1` 验证订单导出\n\n"
            "- 关联验收：`AC-1`\n"
            "- 为什么测：证明验收能通过真实入口和证据闭环。\n"
            "- 项目语义依据：页面：/orders；接口：/api/orders/export。\n"
            "- 怎么造数：测试夹具/工厂方法；数据记录：订单主记录。\n"
            "- 怎么执行：页面路径：打开 /orders -> 点击导出；详细步骤：设置筛选条件并导出。\n"
            "- 怎么判定通过：导出文件包含订单号和状态。\n"
            "- 预期结果：导出成功。\n\n"
            "## 八、追踪关系\n\n"
            "- 追踪到 `spec.json`。\n\n"
            "## 九、证据引用\n\n"
            "- `test_design.json`\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc)
        assert result["decision"] != "block"
        sources = {item["source"] for item in result["blockers"]}
        assert not {"test_execution_path", "test_assertions", "test_data_setup"} & sources


def test_human_doc_review_warns_missing_formal_sections_and_diagram() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        doc.write_text(
            "Scope\nDecision\nOptions\nRisk\nEvidence\nRollback\n"
            "`spec.json`\n"
            "This is readable but still lacks several formal review sections and any chart.\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc)
        assert result["decision"] == "warn"
        sources = {item["source"] for item in result["warnings"]}
        assert "diagram" in sources
        assert "background" in sources


def test_human_doc_review_warns_outline_only_document() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        doc.write_text(
            "# Delivery Review\n\n"
            "## Summary\n\n"
            "- Scope\n- Decision\n- Options\n- Risk\n- Evidence\n- Rollback\n"
            "- Background\n- Goal\n- Clarification\n- Acceptance\n- Test\n"
            "`spec.json`\n\n"
            "```mermaid\nflowchart LR\nA-->B\n```\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc)
        assert result["decision"] == "warn"
        sources = {item["source"] for item in result["warnings"]}
        assert "review_focus" in sources
        assert "bullet_depth" in sources


def test_human_doc_review_warns_chinese_doc_with_english_template_terms() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        doc.write_text(
            "# 中文文档\n\n"
            "## Executive Summary\n\n"
            "背景 目标 范围 澄清 决策 方案 风险 证据 验收 测试 回滚。\n"
            "这里包含足够多的中文内容，用来模拟用户明确要求中文但文档仍残留英文模板标题的情况。\n"
            "这里继续补充中文说明，确保超过语言质量检查阈值。\n"
            "`spec.json`\n\n"
            "```mermaid\nflowchart LR\nA-->B\n```\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc)
        assert result["decision"] == "warn"
        assert any(item["source"] == "zh_language_quality" for item in result["warnings"])


def test_human_doc_review_tracks_unresolved_items_with_context() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "human/designs/REQ-CONFIRM.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "# 续期优化 技术设计\n\n"
            "## 一、摘要\n\n"
            "范围 决策 方案 风险 证据 回滚 测试 追踪 实施边界 评审重点。\n\n"
            "本设计用于评审续期相关数据口径的落地方式，重点说明哪些内容已经确认，哪些内容需要在实施前通过代码和数据库结构核对。"
            "确认项不会被当作最终事实，而是作为设计评审中的显式行动项绑定到证据和责任边界，避免把占位内容包装成已确认结论。\n\n"
            "## 二、候选方案、对比与决策\n\n"
            "### 技术候选方案详述\n\n"
            "- 方案：在责任模块内实现，保持既有接口契约，先通过代码核对真实表名、字段类型和历史数据影响，再进入实现。\n\n"
            "### 技术方案加权对比\n\n"
            "- 风险、证据、回滚均已比较；当前方案胜出是因为回滚边界最小，且未引入跨系统契约变更。\n\n"
            "### 技术决策结论\n\n"
            "- 决策：选择当前责任模块；接受的取舍是实施前必须完成表结构核对，否则不得把字段变更作为已确认实现任务。\n\n"
            "## 三、数据模型与表结构\n\n"
            "- 表：需结合代码和数据库核对；原因：当前项目理解没有可靠表名；动作：实施前核对 mapper 和 migration；证据：`technical_design.json`。\n\n"
            "## 四、风险与回滚\n\n"
            "- 风险：表结构需核对。回滚：按 migration 策略回滚；如发现真实表结构不支持无损回滚，应回到设计阶段重新选择方案。\n\n"
            "## 五、测试策略摘要\n\n"
            "- 测试：覆盖功能、回归和数据兼容。\n\n"
            "## 六、追踪关系\n\n"
            "- 追踪到 `spec.json`、`technical_design.json` 和 `test_design.json`。\n\n"
            "```mermaid\nflowchart LR\nA-->B\n```\n\n"
            "```mermaid\nsequenceDiagram\nparticipant A\nparticipant B\nA->>B: 核对表结构\n```\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc, strict=True)
        assert result["decision"] != "block"
        assert result["unresolved_summary"]["count"] == 1
        assert not any(item["source"] == "unresolved_without_context" for item in result["blockers"])


def test_human_doc_review_blocks_unresolved_items_without_context_in_strict_mode() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "human/designs/REQ-CONFIRM.md"
        doc.parent.mkdir(parents=True)
        doc.write_text(
            "# 续期优化 技术设计\n\n"
            "## 一、摘要\n\n"
            "范围 决策 方案 风险 证据 回滚 测试 追踪 实施边界 评审重点。\n\n"
            "本设计模拟缺少确认项上下文的情况。文档包含基本评审章节，但故意没有给确认项绑定原因、动作或证据，严格模式应阻止它进入共享评审。\n\n"
            "## 二、候选方案、对比与决策\n\n"
            "### 技术候选方案详述\n\n"
            "- 方案：在责任模块内实现，保持既有接口契约，控制变更范围并降低回滚成本。\n\n"
            "### 技术方案加权对比\n\n"
            "- 风险、证据、回滚均已比较；当前方案的主要优势是边界清晰，主要风险是结构信息仍不充分。\n\n"
            "### 技术决策结论\n\n"
            "- 决策：选择当前责任模块；但下方确认项没有给出处置上下文，因此应被文档门禁识别。\n\n"
            "## 三、数据模型与表结构\n\n"
            "- 表：需结合代码和数据库核对。\n\n"
            "## 四、风险与回滚\n\n"
            "- 风险：表结构需核对。回滚：按 migration 策略回滚；如果真实结构不支持回滚，需要重新评审数据方案。\n\n"
            "## 五、测试策略摘要\n\n"
            "- 测试：覆盖功能、回归和数据兼容。\n\n"
            "## 六、追踪关系\n\n"
            "- 追踪到 `spec.json`、`technical_design.json` 和 `test_design.json`。\n\n"
            "```mermaid\nflowchart LR\nA-->B\n```\n",
            encoding="utf-8",
        )
        result = human_doc_review.review(doc, strict=True)
        assert result["decision"] == "block"
        assert any(item["source"] == "unresolved_without_context" for item in result["blockers"])


def test_forward_test_runner_passes_synthetic_case() -> None:
    result = forward_test.run(ROOT)
    assert result["schema"] == "codex-forward-test-run-v1"
    assert result["decision"] == "pass"
    assert result["cases"][0]["passed"] is True
    assert result["cases"][0]["blocked_case_passed"] is True
    assert result["cases"][0]["happy_path_case_passed"] is True
    assert all(result["cases"][0]["scenario_results"].values())
    shape_results = result["cases"][0]["requirement_shape_results"]
    assert shape_results["details"] == {
        "one_line_decision": "blocked",
        "long_prd_decision": "ready_for_design",
        "vague_bugfix_decision": "blocked",
        "resolved_bugfix_decision": "ready_for_design",
    }


def test_scenario_catalog_documents_supported_development_scenarios() -> None:
    result = scenario_catalog.catalog()
    scenario_ids = {item["id"] for item in result["scenarios"]}
    assert {
        "one_line_request",
        "long_prd",
        "bugfix",
        "frontend_change",
        "cross_repo_api",
        "data_migration",
        "release_readiness",
        "code_review",
    }.issubset(scenario_ids)
    guide = (ROOT / "docs/scenario-guide.md").read_text(encoding="utf-8")
    for scenario_id in scenario_ids:
        assert scenario_id in guide
    matrix = result["coverage_matrix"]
    assert len(matrix) == result["scenario_count"]
    matrix_by_id = {item["scenario_id"]: item for item in matrix}
    for scenario_id in scenario_ids:
        assert matrix_by_id[scenario_id]["required_skills"]
        assert matrix_by_id[scenario_id]["required_gates"]
    for scenario_id in {"one_line_request", "long_prd", "frontend_change", "cross_repo_api", "data_migration"}:
        gates = set(matrix_by_id[scenario_id]["required_gates"])
        assert {"technical_design.json", "architecture_design.json", "test_design.json", "docs_quality.json", "git_worktree_evidence.json", "edit_permit.json"}.issubset(gates)
        anti_bypass = " ".join(matrix_by_id[scenario_id]["anti_bypass"])
        assert "pull --ff-only" in anti_bypass
    bugfix_gates = set(matrix_by_id["bugfix"]["required_gates"])
    assert {"spec.json", "technical_design.json", "test_design.json", "delivery_plan_review.json", "docs_quality.json"}.issubset(bugfix_gates)
    assert "architecture_design.json" not in bugfix_gates
    assert "test_data_plan.json" in bugfix_gates
    for item in result["scenarios"]:
        if item["id"] in {"one_line_request", "long_prd", "cross_repo_api", "data_migration"}:
            next_step = item["next_step"]
            assert "technical_design.json" in next_step
            assert "architecture_design.json" in next_step
            assert "pull --ff-only" in next_step
            assert "edit_permit.json" in next_step
            assert "write_guard_snapshot.json" in next_step
            assert "write_guard_audit.json" in next_step
        if item["id"] == "bugfix":
            assert "effective_workflow_controls" in item["next_step"]
            assert "architecture_design.json" not in item["evidence"]


def test_codex_eng_scenarios_cli_runs() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/codex_eng.py", "scenarios"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    assert "codex-scenario-catalog-v1" in proc.stdout


def test_codex_eng_docs_governor_passthrough_runs() -> None:
    config_file = ROOT / ".codex-engineering-docs.json"
    original = config_file.read_text(encoding="utf-8") if config_file.exists() else None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, "scripts/codex_eng.py", "run", "docs-governor", "init", "--docs-root", tmp, "--doc-id", "REQ-DOCS"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            assert proc.returncode == 0
            assert "codex-docs-governor-v1" in proc.stdout
    finally:
        if original is None:
            config_file.unlink(missing_ok=True)
        else:
            config_file.write_text(original, encoding="utf-8")


def test_codex_eng_docs_configure_cli_runs() -> None:
    config_file = ROOT / ".codex-engineering-docs.json"
    original = config_file.read_text(encoding="utf-8") if config_file.exists() else None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, "scripts/codex_eng.py", "docs", "configure", "--docs-root", tmp],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            assert proc.returncode == 0
            assert "codex-docs-workspace-config-v1" in proc.stdout
            assert config_file.exists()
    finally:
        if original is None:
            config_file.unlink(missing_ok=True)
        else:
            config_file.write_text(original, encoding="utf-8")


def test_codex_eng_doctor_cli_runs() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/codex_eng.py", "doctor"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    assert "codex-doctor-v1" in proc.stdout


def test_codex_eng_doctor_human_cli_runs() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/codex_eng.py", "doctor", "--format", "human"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    assert "Codex doctor" in proc.stdout


def test_codex_eng_setup_dry_run_cli_runs() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/codex_eng.py", "setup"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0
    assert "Codex setup" in proc.stdout
    assert "dry_run" in proc.stdout


def test_codex_eng_next_human_cli_runs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        artifact_dir = Path(tmp) / "artifacts"
        artifact_dir.mkdir()
        proc = subprocess.run(
            [sys.executable, "scripts/codex_eng.py", "next", "--artifact-dir", str(artifact_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 2
        assert "Codex delivery status" in proc.stdout
        assert "next_stage" in proc.stdout


def test_implement_dry_run_blocks_missing_gates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = implement_dry_run.run(Path(tmp))
        assert result["schema"] == "codex-implement-dry-run-v1"
        assert result["decision"] == "blocked"
        assert "delivery_plan.json" in result["missing_gates"]


def write_ready_design_gates(root: Path) -> None:
    (root / "spec.json").write_text('{ "decision": "ready_for_design" }', encoding="utf-8")
    (root / "technical_design.json").write_text('{ "schema": "codex-technical-design-v1" }', encoding="utf-8")
    (root / "architecture_design.json").write_text('{ "schema": "codex-architecture-design-v1" }', encoding="utf-8")
    (root / "test_design.json").write_text('{ "decision": "pass", "test_cases": [{ "id": "TC-1" }] }', encoding="utf-8")
    (root / "docs_quality.json").write_text('{ "decision": "pass", "blockers": [] }', encoding="utf-8")
    (root / "design_architecture_review.json").write_text(
        '{ "decision": "pass", "readiness_gate": { "implementation_allowed": true } }',
        encoding="utf-8",
    )
    (root / "delivery_plan_review.json").write_text(
        '{ "decision": "pass", "readiness_gate": { "implementation_allowed": true } }',
        encoding="utf-8",
    )
    runtime = implement_dry_run.AGENT_RUNTIME
    runtime.start(root, "REQ-1", "small_feature")
    runtime.append_event(root, "requirement_ingested", "test-fixture")
    runtime.checkpoint(root, "intake", ["spec.json"])
    runtime.append_event(root, "design_completed", "test-fixture")
    runtime.checkpoint(root, "design", ["technical_design.json", "architecture_design.json"])
    verification = runtime.verify(root)
    (root / "harness_validation.json").write_text(json.dumps({
        "schema": "codex-harness-checkpoint-v2",
        "checkpoint": "design",
        "decision": "pass",
        "blockers": [],
        "checkpoints": [{"checkpoint": "design", "decision": "pass"}],
        "session_id": verification["session_id"],
        "runtime_root_digest": verification["event_root_digest"],
        "event_refs": ["technical_design.json", "architecture_design.json"],
    }), encoding="utf-8")


def test_implement_dry_run_allows_scoped_ready_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        implement_dry_run.DOCS_GOVERNOR.init(docs_root, "REQ-1")
        write_ready_design_gates(root)
        (root / "delivery_plan.json").write_text(
            '{ "doc_id": "REQ-1", "repo_tasks": [{ "role": "modify", "repo": "app", "repo_path": ".", "allowed_files": ["src/app.py"], "test_commands": ["pytest"] }] }',
            encoding="utf-8",
        )
        (root / "git_worktree_evidence.json").write_text('{ "decision": "ready", "fetched": true, "base_updated": true }', encoding="utf-8")
        (root / "edit_permit.json").write_text('{ "decision": "ready" }', encoding="utf-8")
        result = implement_dry_run.run(root, docs_root=docs_root)
        assert result["decision"] == "ready"
        assert result["can_edit"] is True
        assert result["docs_readiness"]["decision"] == "pass"
        assert result["allowed_files"] == ["src/app.py"]
        assert result["recommended_validation_commands"] == ["pytest"]


def test_implement_dry_run_blocks_without_design_chain_even_if_git_ready() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        implement_dry_run.DOCS_GOVERNOR.init(docs_root, "REQ-1")
        (root / "delivery_plan.json").write_text(
            '{ "doc_id": "REQ-1", "repo_tasks": [{ "role": "modify", "allowed_files": ["src/app.py"] }] }',
            encoding="utf-8",
        )
        (root / "git_worktree_evidence.json").write_text('{ "decision": "ready", "fetched": true, "base_updated": true }', encoding="utf-8")
        (root / "edit_permit.json").write_text('{ "decision": "ready" }', encoding="utf-8")
        result = implement_dry_run.run(root, docs_root=docs_root)
        assert result["decision"] == "blocked"
        assert "technical_design.json" in result["missing_gates"]
        assert "architecture_design.json" in result["missing_gates"]
        assert "test_design.json" in result["missing_gates"]
        assert "docs_quality.json" in result["missing_gates"]
        assert "design_architecture_review.json" in result["missing_gates"]


def test_implement_dry_run_blocks_without_test_design() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        manifest = docs_root / "indexes/REQ-1.manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
        write_ready_design_gates(root)
        (root / "test_design.json").unlink()
        (root / "delivery_plan.json").write_text(
            '{ "doc_id": "REQ-1", "repo_tasks": [{ "role": "modify", "allowed_files": ["src/app.py"] }] }',
            encoding="utf-8",
        )
        (root / "git_worktree_evidence.json").write_text('{ "decision": "ready", "fetched": true, "base_updated": true }', encoding="utf-8")
        (root / "edit_permit.json").write_text('{ "decision": "ready" }', encoding="utf-8")
        result = implement_dry_run.run(root, docs_root=docs_root)
        assert result["decision"] == "blocked"
        assert "test_design.json" in result["missing_gates"]


def test_implement_dry_run_blocks_when_docs_quality_warns() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        manifest = docs_root / "indexes/REQ-1.manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
        write_ready_design_gates(root)
        (root / "docs_quality.json").write_text('{ "decision": "warn", "warnings": [{ "source": "depth" }] }', encoding="utf-8")
        (root / "delivery_plan.json").write_text(
            '{ "doc_id": "REQ-1", "repo_tasks": [{ "role": "modify", "allowed_files": ["src/app.py"] }] }',
            encoding="utf-8",
        )
        (root / "git_worktree_evidence.json").write_text('{ "decision": "ready", "fetched": true, "base_updated": true }', encoding="utf-8")
        (root / "edit_permit.json").write_text('{ "decision": "ready" }', encoding="utf-8")
        result = implement_dry_run.run(root, docs_root=docs_root)
        assert result["decision"] == "blocked"
        assert "docs_quality.json is not ready" in result["missing_gates"]


def test_implement_dry_run_requires_git_fetch_and_pull_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        manifest = docs_root / "indexes/REQ-1.manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
        write_ready_design_gates(root)
        (root / "delivery_plan.json").write_text(
            '{ "doc_id": "REQ-1", "repo_tasks": [{ "role": "modify", "allowed_files": ["src/app.py"] }] }',
            encoding="utf-8",
        )
        (root / "git_worktree_evidence.json").write_text('{ "decision": "ready" }', encoding="utf-8")
        (root / "edit_permit.json").write_text('{ "decision": "ready" }', encoding="utf-8")
        result = implement_dry_run.run(root, docs_root=docs_root)
        assert result["decision"] == "blocked"
        assert any("git fetch evidence is missing" in item for item in result["missing_gates"])
        assert any("git pull --ff-only evidence is missing" in item for item in result["missing_gates"])


def test_implement_dry_run_blocks_staging_repo_bindings() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        implement_dry_run.DOCS_GOVERNOR.init(docs_root, "REQ-1")
        write_ready_design_gates(root)
        staging_repo = root / "_staging" / "repo"
        (root / "delivery_plan.json").write_text(
            json.dumps({
                "doc_id": "REQ-1",
                "repo_tasks": [
                    {
                        "role": "modify",
                        "repo": "app",
                        "repo_path": str(staging_repo),
                        "allowed_files": ["src/app.py"],
                    }
                ],
            }),
            encoding="utf-8",
        )
        (root / "git_worktree_evidence.json").write_text(
            json.dumps({"decision": "ready", "repo": str(staging_repo), "fetched": True, "base_updated": True}),
            encoding="utf-8",
        )
        (root / "edit_permit.json").write_text(
            json.dumps({"decision": "ready", "repo": str(staging_repo)}),
            encoding="utf-8",
        )
        result = implement_dry_run.run(root, docs_root=docs_root)
        assert result["decision"] == "blocked"
        assert any("_staging" in item for item in result["missing_gates"])


def test_implement_dry_run_requires_docs_git_repo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        manifest = docs_root / "indexes/REQ-1.manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}", encoding="utf-8")
        write_ready_design_gates(root)
        (root / "delivery_plan.json").write_text(
            '{ "doc_id": "REQ-1", "repo_tasks": [{ "role": "modify", "allowed_files": ["src/app.py"] }] }',
            encoding="utf-8",
        )
        (root / "git_worktree_evidence.json").write_text('{ "decision": "ready", "fetched": true, "base_updated": true }', encoding="utf-8")
        (root / "edit_permit.json").write_text('{ "decision": "ready" }', encoding="utf-8")
        result = implement_dry_run.run(root, docs_root=docs_root)
        assert result["decision"] == "blocked"
        assert "docs: docs root must be a git repository" in result["missing_gates"]


def test_implement_dry_run_accepts_git_plan_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = root / "delivery-docs"
        implement_dry_run.DOCS_GOVERNOR.init(docs_root, "REQ-1")
        write_ready_design_gates(root)
        (root / "delivery_plan.json").write_text(
            '{ "doc_id": "REQ-1", "repo_tasks": [{ "role": "modify", "repo": "api", "allowed_files": ["api/app.py"] }, { "role": "modify", "repo": "web", "allowed_files": ["web/app.ts"] }] }',
            encoding="utf-8",
        )
        (root / "git_plan_baseline_summary.json").write_text(
            json.dumps({
                "decision": "ready",
                "results": [
                    {"decision": "ready", "repo_name": "api", "fetched": True, "base_updated": True},
                    {"decision": "ready", "repo_name": "web", "fetched": True, "base_updated": True},
                ],
            }),
            encoding="utf-8",
        )
        (root / "edit_permit.json").write_text('{ "decision": "ready" }', encoding="utf-8")
        result = implement_dry_run.run(root, docs_root=docs_root)
        assert result["decision"] == "ready"
        assert result["git_evidence_count"] == 2


def test_implement_dry_run_uses_configured_docs_root_by_default() -> None:
    config_file = ROOT / ".codex-engineering-docs.json"
    original = config_file.read_text(encoding="utf-8") if config_file.exists() else None
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs_root = root / "delivery-docs"
            implement_dry_run.DOCS_GOVERNOR.init(docs_root, "REQ-1")
            config_file.write_text(json.dumps({"schema": "codex-docs-workspace-config-v1", "docs_root": str(docs_root)}), encoding="utf-8")
            write_ready_design_gates(root)
            (root / "delivery_plan.json").write_text(
                '{ "doc_id": "REQ-1", "repo_tasks": [{ "role": "modify", "allowed_files": ["src/app.py"] }] }',
                encoding="utf-8",
            )
            (root / "git_worktree_evidence.json").write_text('{ "decision": "ready", "fetched": true, "base_updated": true }', encoding="utf-8")
            (root / "edit_permit.json").write_text('{ "decision": "ready" }', encoding="utf-8")
            result = implement_dry_run.run(root)
            assert result["decision"] == "ready"
            assert result["docs_readiness"]["docs_root"] == str(docs_root)
    finally:
        if original is None:
            config_file.unlink(missing_ok=True)
        else:
            config_file.write_text(original, encoding="utf-8")


def test_codex_eng_implement_dry_run_cli_runs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [sys.executable, "scripts/codex_eng.py", "implement", "--artifact-dir", tmp],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 2
        assert "Codex implement dry-run" in proc.stdout
        assert "missing_gates" in proc.stdout


def test_benchmark_reports_scenario_coverage_metrics() -> None:
    result = benchmark.report(ROOT)
    metrics = result["metrics"]
    assert result["decision"] == "pass"
    assert metrics["workflow_profile_count"] >= 6
    assert metrics["setup_command_available"] is True
    assert metrics["next_command_available"] is True
    assert metrics["implement_dry_run_available"] is True
    assert metrics["human_output_available"] is True
    assert metrics["profile_scoring_available"] is True
    assert metrics["scenario_count"] >= 8
    assert metrics["scenario_catalog_count"] >= 8
    assert metrics["scenario_count"] == metrics["scenario_catalog_count"]
    assert metrics["scenario_matrix_count"] == metrics["scenario_catalog_count"]
    assert metrics["scenario_matrix_gate_coverage_count"] == metrics["scenario_catalog_count"]
    assert metrics["documented_scenario_count"] == metrics["scenario_catalog_count"]
    assert metrics["forward_tested_scenario_count"] >= 8
    assert metrics["skill_advanced_or_better_count"] > 0
    assert metrics["skill_expert_readiness"] in {"expert", "advanced", "mixed"}
    assert metrics["skill_content_quality_average"] > 0
    assert metrics["skill_content_quality_expert_count"] > 0
    assert metrics["replay_validation_decision"] == "pass"
    assert metrics["replay_case_count"] >= 7
    assert metrics["replay_scenario_count"] >= 7
    assert metrics["replay_complex_case_count"] >= 3
    assert metrics["replay_scenario_family_coverage_count"] >= 5
    assert metrics["replay_behavior_coverage_score"] >= 80
    assert metrics["cross_repo_planner_available"] is True
    assert metrics["cross_repo_example_decision"] == "ready"
    assert metrics["cross_repo_graph_validation_decision"] == "pass"
    assert metrics["cross_repo_cycle_block_test_available"] is True
    assert metrics["cross_repo_profile_artifact_step_available"] is True
    assert metrics["cross_repo_auto_runner_generation_available"] is True


def run_all() -> None:
    test_skill_health_runs_on_repo()
    test_root_skill_health_wrapper_exists_for_readme_command()
    test_all_skill_docs_declare_output_section()
    test_all_skill_docs_declare_taxonomy_frontmatter()
    test_skill_health_blocks_invalid_expert_gate_metadata()
    test_workflow_profiles_reference_existing_skills()
    test_readme_uses_current_validation_commands()
    test_docs_describe_full_pre_edit_gate()
    test_architecture_documents_skill_taxonomy_and_gate_contract()
    test_skill_catalog_lists_all_skills_with_maturity()
    test_previously_b_level_skill_docs_have_operational_guidance()
    test_final_target_skill_docs_have_operational_guidance()
    test_skill_quality_distribution_is_all_a_level()
    test_overlay_health_blocks_missing_registry()
    test_overlay_health_blocks_missing_declared_assets_and_warns_stale_assets()
    test_overlay_health_reviews_project_skill_guidance_quality()
    test_overlay_health_policy_can_require_team_sections()
    test_overlay_health_supports_installed_company_layout_and_json_registry()
    test_overlay_health_skips_declared_tool_skills()
    test_human_doc_review_detects_local_path()
    test_human_doc_review_warns_thin_doc()
    test_human_doc_review_strict_blocks_warnings()
    test_human_doc_review_strict_is_doc_type_aware_for_specs()
    test_human_doc_review_strict_requires_design_depth_for_designs()
    test_human_doc_review_blocks_design_decision_before_options()
    test_human_doc_review_strict_is_doc_type_aware_for_tests()
    test_human_doc_review_blocks_chinese_test_doc_without_execution_details()
    test_human_doc_review_accepts_review_style_test_case_sections()
    test_human_doc_review_warns_missing_formal_sections_and_diagram()
    test_human_doc_review_warns_outline_only_document()
    test_human_doc_review_warns_chinese_doc_with_english_template_terms()
    test_forward_test_runner_passes_synthetic_case()
    test_scenario_catalog_documents_supported_development_scenarios()
    test_codex_eng_scenarios_cli_runs()
    test_codex_eng_docs_governor_passthrough_runs()
    test_codex_eng_docs_configure_cli_runs()
    test_codex_eng_doctor_cli_runs()
    test_codex_eng_doctor_human_cli_runs()
    test_codex_eng_setup_dry_run_cli_runs()
    test_codex_eng_next_human_cli_runs()
    test_implement_dry_run_blocks_missing_gates()
    test_implement_dry_run_allows_scoped_ready_artifacts()
    test_implement_dry_run_blocks_without_test_design()
    test_implement_dry_run_blocks_when_docs_quality_warns()
    test_implement_dry_run_requires_git_fetch_and_pull_evidence()
    test_implement_dry_run_blocks_staging_repo_bindings()
    test_implement_dry_run_requires_docs_git_repo()
    test_implement_dry_run_accepts_git_plan_summary()
    test_implement_dry_run_uses_configured_docs_root_by_default()
    test_codex_eng_implement_dry_run_cli_runs()
    test_benchmark_reports_scenario_coverage_metrics()


if __name__ == "__main__":
    run_all()
    print("PASS health_and_forward tests")
