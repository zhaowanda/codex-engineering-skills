from pathlib import Path

import importlib.util
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "core" / "delivery-state-governor" / "scripts" / "delivery_state.py"
spec = importlib.util.spec_from_file_location("delivery_state", SCRIPT)
delivery_state = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules["delivery_state"] = delivery_state
spec.loader.exec_module(delivery_state)


def test_bugfix_requires_reproduction_before_implementation(tmp_path: Path) -> None:
    state = delivery_state.init_state("BUG-1", "bugfix", tmp_path)
    assert state["schema"] == "codex-delivery-state-v1"
    result = delivery_state.validate_state(tmp_path / "delivery_state.json", "implementation")
    assert result["decision"] == "blocked"
    assert "reproduction" in result["missing_gates"]
    assert "git" in result["missing_gates"]


def test_standard_requirement_reaches_release_ready(tmp_path: Path) -> None:
    delivery_state.init_state("REQ-1", "standard_requirement", tmp_path)
    state_path = tmp_path / "delivery_state.json"
    for gate in [
        "spec",
        "technical_design",
        "architecture_design",
        "delivery_plan",
        "docs_quality",
        "design_review",
        "freeze",
        "git",
        "implementation",
        "review",
        "test",
        "release",
    ]:
        delivery_state.advance_state(state_path, gate, gate, f"{gate}.json")
    result = delivery_state.validate_state(state_path, "release")
    assert result["decision"] == "ready"


def test_block_and_unblock(tmp_path: Path) -> None:
    delivery_state.init_state("REQ-2", "small_change", tmp_path)
    state_path = tmp_path / "delivery_state.json"
    delivery_state.block_state(state_path, "open question", "answer question")
    blocked = delivery_state.validate_state(state_path, "implementation")
    assert blocked["decision"] == "blocked"
    assert "open question" in blocked["blockers"]
    delivery_state.unblock_state(state_path, "answered", "answers.json")
    unblocked = delivery_state.inspect_state(state_path)
    assert unblocked["status"] == "ready"
    assert unblocked["blockers"] == []


def test_repo_states_are_recorded_and_block_validation(tmp_path: Path) -> None:
    state = delivery_state.init_state("REQ-MULTI", "standard_requirement", tmp_path, ["provider", "consumer"])
    assert [item["repo"] for item in state["repo_states"]] == ["provider", "consumer"]
    state_path = tmp_path / "delivery_state.json"
    state["repo_states"][1]["status"] = "blocked"
    state["repo_states"][1]["blockers"] = ["provider contract not frozen"]
    delivery_state.write_json(state_path, state)
    result = delivery_state.validate_state(state_path, "implementation")
    assert result["decision"] == "blocked"
    assert any("consumer" in item for item in result["blockers"])


def test_repo_states_require_declared_git_and_edit_permit_evidence(tmp_path: Path) -> None:
    state = delivery_state.init_state("REQ-MULTI", "standard_requirement", tmp_path, ["provider"])
    state_path = tmp_path / "delivery_state.json"
    state["repo_states"][0]["requires_git"] = True
    state["repo_states"][0]["requires_edit_permit"] = True
    delivery_state.write_json(state_path, state)
    result = delivery_state.validate_state(state_path, "implementation")
    assert result["decision"] == "blocked"
    assert any("git evidence" in item for item in result["blockers"])
    assert any("edit permit" in item for item in result["blockers"])
    state["repo_states"][0]["evidence"] = {"git": "git.json", "edit_permit": "edit_permit.json"}
    for gate in [
        "spec",
        "technical_design",
        "architecture_design",
        "delivery_plan",
        "docs_quality",
        "design_review",
        "freeze",
        "git",
    ]:
        if gate not in state["passed_gates"]:
            state["passed_gates"].append(gate)
    delivery_state.write_json(state_path, state)
    ready = delivery_state.validate_state(state_path, "implementation")
    assert ready["decision"] == "ready"


def test_release_requires_completed_integration_gates(tmp_path: Path) -> None:
    state = delivery_state.init_state("REQ-MULTI", "standard_requirement", tmp_path, ["provider", "consumer"])
    state_path = tmp_path / "delivery_state.json"
    state["passed_gates"] = [
        "doc_id",
        "spec",
        "technical_design",
        "architecture_design",
        "delivery_plan",
        "git",
        "implementation",
        "review",
        "test",
        "release",
    ]
    state["integration_gates"] = [{"gate": "cross_repo_integration_test", "status": "pending"}]
    delivery_state.write_json(state_path, state)
    result = delivery_state.validate_state(state_path, "release")
    assert result["decision"] == "blocked"
    assert any("cross_repo_integration_test" in item for item in result["blockers"])
    state["integration_gates"][0]["status"] = "passed"
    delivery_state.write_json(state_path, state)
    ready = delivery_state.validate_state(state_path, "release")
    assert ready["decision"] == "ready"


def run_all() -> None:
    import tempfile

    tests = [
        test_bugfix_requires_reproduction_before_implementation,
        test_standard_requirement_reaches_release_ready,
        test_block_and_unblock,
        test_repo_states_are_recorded_and_block_validation,
        test_repo_states_require_declared_git_and_edit_permit_evidence,
        test_release_requires_completed_integration_gates,
    ]
    for test in tests:
        with tempfile.TemporaryDirectory() as tmp:
            test(Path(tmp))


if __name__ == "__main__":
    run_all()
    print("PASS delivery_state tests")
