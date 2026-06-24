from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


sync_local = load_module("sync_local_skills", ROOT / "scripts/sync_local_skills.py")


def write_skill(path: Path, name: str) -> None:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n\n# {name}\n", encoding="utf-8")


def test_sync_copies_open_repo_and_preserves_private_overlay() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = root / "repo"
        skills_root = root / "codex" / "skills"
        write_skill(repo / "skills/core/git-worktree-governor", "git-worktree-governor")
        write_skill(repo / "skills/core/new-open-skill", "new-open-skill")
        write_skill(repo / "skills/templates/design-doc-templates", "design-doc-templates")
        write_skill(skills_root / "company/git-worktree-governor", "git-worktree-governor")
        write_skill(skills_root / "company/private-project", "private-project")

        plan = sync_local.sync(repo, skills_root, dry_run=True, force=True, mode="copy")
        assert plan["decision"] == "plan"
        assert plan["action_count"] == 3

        result = sync_local.sync(repo, skills_root, dry_run=False, force=True, mode="copy")
        assert result["decision"] == "pass"
        assert not (skills_root / "codex-engineering-skills/git-worktree-governor").is_symlink()
        assert not (skills_root / "codex-engineering-skills/new-open-skill").is_symlink()
        assert not (skills_root / "codex-engineering-skills/design-doc-templates").is_symlink()
        assert (skills_root / "codex-engineering-skills/git-worktree-governor/.codex-engineering-skills-source").exists()
        assert (skills_root / "codex-engineering-skills/new-open-skill/SKILL.md").exists()
        assert (skills_root / "codex-engineering-skills/design-doc-templates/SKILL.md").exists()
        assert (skills_root / "company/private-project/SKILL.md").exists()
        assert not (skills_root / ".backup").exists()

        second = sync_local.sync(repo, skills_root, dry_run=True, force=False, mode="copy")
        assert second["decision"] == "plan"
        assert second["already_installed_count"] == 3

        forced = sync_local.sync(repo, skills_root, dry_run=True, force=True, mode="copy")
        assert forced["decision"] == "plan"
        assert forced["installed_count"] == 3


def test_prune_legacy_archives_non_open_source_entries() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        skills_root = Path(tmp) / "skills"
        write_skill(skills_root / ".system/skill-creator", "skill-creator")
        write_skill(skills_root / "codex-engineering-skills/core/spec-governor", "spec-governor")
        write_skill(skills_root / "company/private-project", "private-project")
        write_skill(skills_root / "sme-ai-delivery/prd-composer", "prd-composer")
        write_skill(skills_root / "open-core/spec-governor", "spec-governor")
        (skills_root / "product-skills-index.md").write_text("legacy\n", encoding="utf-8")

        plan = sync_local.prune_legacy(skills_root, dry_run=True, force=False)
        assert plan["decision"] == "plan"
        assert any(item["status"] == "would_archive" for item in plan["actions"])

        result = sync_local.prune_legacy(skills_root, dry_run=False, force=True)
        assert result["decision"] == "pass"
        assert (skills_root / ".system/skill-creator/SKILL.md").exists()
        assert (skills_root / "codex-engineering-skills/core/spec-governor/SKILL.md").exists()
        assert not (skills_root / "company").exists()
        assert not (skills_root / "sme-ai-delivery").exists()
        assert not (skills_root / "open-core").exists()
        assert not (skills_root / "product-skills-index.md").exists()
        assert (skills_root / ".backup/codex-engineering-skills-prune").exists()


def run_all() -> None:
    test_sync_copies_open_repo_and_preserves_private_overlay()
    test_prune_legacy_archives_non_open_source_entries()


if __name__ == "__main__":
    run_all()
    print("PASS local_skill_sync tests")
