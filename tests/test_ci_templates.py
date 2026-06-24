from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/templates/ci-templates/scripts/render_ci.py"
spec = importlib.util.spec_from_file_location("render_ci", SCRIPT)
render_ci = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(render_ci)


def test_render_github_contains_validation_steps() -> None:
    content = render_ci.render("github")
    assert "actions/checkout@v4" in content
    assert "py_compile" in content
    assert "tests/test_*.py" in content or "glob('test_*.py')" in content
    assert "privacy_scan.py" in content
    assert "skill_health.py" in content


def test_render_gitlab_contains_validation_steps() -> None:
    content = render_ci.render("gitlab")
    assert "image: python:3.11" in content
    assert "py_compile" in content
    assert "privacy_scan.py" in content
    assert "skill_health.py" in content
    assert "merge_request_event" in content


def test_main_writes_output_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / ".github/workflows/validate.yml"
        content = render_ci.render("github")
        out.parent.mkdir(parents=True)
        out.write_text(content, encoding="utf-8")
        assert out.exists()
        assert "name: validate" in out.read_text(encoding="utf-8")


def run_all() -> None:
    test_render_github_contains_validation_steps()
    test_render_gitlab_contains_validation_steps()
    test_main_writes_output_file()


if __name__ == "__main__":
    run_all()
    print("PASS ci_templates tests")
