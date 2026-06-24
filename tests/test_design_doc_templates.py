from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_SCRIPT = ROOT / "skills/templates/design-doc-templates/scripts/render_design_templates.py"
REVIEW_SCRIPT = ROOT / "skills/core/design-architecture-reviewer/scripts/design_arch_review.py"

template_spec = importlib.util.spec_from_file_location("render_design_templates", TEMPLATE_SCRIPT)
render_design_templates = importlib.util.module_from_spec(template_spec)
assert template_spec.loader
template_spec.loader.exec_module(render_design_templates)

review_spec = importlib.util.spec_from_file_location("design_arch_review", REVIEW_SCRIPT)
design_arch_review = importlib.util.module_from_spec(review_spec)
assert review_spec.loader
review_spec.loader.exec_module(design_arch_review)


def test_empty_templates_have_required_top_level_sections() -> None:
    technical = render_design_templates.empty_technical("REQ-1", "Title")
    architecture = render_design_templates.empty_architecture("REQ-1", "Title")
    for key in ["process_flow", "module_decomposition", "logical_data_flow", "solution_options", "selected_solution", "design_traceability_matrix"]:
        assert key in technical
    for key in ["architecture_options", "selected_architecture", "component_boundaries", "module_topology", "repo_responsibilities", "rollback_strategy"]:
        assert key in architecture


def test_example_templates_pass_design_reviewer() -> None:
    technical = render_design_templates.example_technical("REQ-1", "Checkout discount display")
    architecture = render_design_templates.example_architecture("REQ-1", "Checkout discount display")
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "pass"
    assert result["readiness_gate"]["implementation_allowed"]


def test_render_writes_manifest_and_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        manifest = render_design_templates.render("REQ-1", "Checkout discount display", out_dir, example=True)
        assert manifest["schema"] == "codex-design-template-manifest-v1"
        assert (out_dir / "technical_design.json").exists()
        assert (out_dir / "architecture_design.json").exists()
        assert (out_dir / "design_template_manifest.json").exists()


def run_all() -> None:
    test_empty_templates_have_required_top_level_sections()
    test_example_templates_pass_design_reviewer()
    test_render_writes_manifest_and_files()


if __name__ == "__main__":
    run_all()
    print("PASS design_doc_templates tests")
