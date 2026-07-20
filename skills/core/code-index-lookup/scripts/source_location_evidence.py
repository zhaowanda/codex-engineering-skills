#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


SCHEMA = "codex-source-location-evidence-v1"
BUNDLE_SCHEMA = "codex-evidence-bundle-v1"
GENERIC_TERMS = {
    "add", "change", "device", "feature", "fix", "page", "service", "update",
    "修改", "功能", "优化", "页面", "设备", "需求", "用户",
}
WEAK_EQUIVALENTS = {"设备": "device", "页面": "page", "服务": "service", "功能": "feature"}
SOURCE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".java", ".kt", ".go", ".rs", ".php", ".rb", ".cs"}
HTTP_METHOD_ROUTE = re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s+((?:/[A-Za-z0-9_{}.*-]+)+)", re.I)
BACKTICK_ROUTE = re.compile(r"`((?:/[A-Za-z0-9_{}.*-]+)+)`")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def overlay_reference_evidence(skill_dir: Path | None, requirement: str, max_files: int = 8, max_hits: int = 24) -> dict[str, Any]:
    if not skill_dir or not skill_dir.is_dir():
        return {
            "skill_dir": str(skill_dir) if skill_dir else "",
            "loaded": False,
            "references": [],
            "reference_digests": {},
            "consumed_rules": [],
            "stale_references": [],
        }
    references_dir = skill_dir / "references"
    terms = [term for term in query_terms(requirement) if term not in GENERIC_TERMS and len(term) >= 3]
    rows: list[dict[str, Any]] = []
    digests: dict[str, str] = {}
    consumed: list[dict[str, Any]] = []
    candidates = [skill_dir / "SKILL.md", *sorted(references_dir.glob("*"))] if references_dir.is_dir() else [skill_dir / "SKILL.md"]
    for path in candidates:
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".yaml", ".yml"}:
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="ignore")
        hits: list[dict[str, Any]] = []
        for number, line in enumerate(text.splitlines(), start=1):
            matched = [term for term in terms if term in line.lower()]
            if matched:
                hits.append({"line": number, "terms": matched[:5], "excerpt": line.strip()[:300]})
            if len(hits) >= 6:
                break
        if not hits:
            continue
        relative = path.relative_to(skill_dir).as_posix()
        digests[relative] = digest_bytes(raw)
        rows.append({"file": relative, "hits": hits, "digest": digests[relative]})
        consumed.extend({"file": relative, **hit} for hit in hits)
        if len(rows) >= max_files or len(consumed) >= max_hits:
            break
    return {
        "skill_dir": str(skill_dir),
        "loaded": True,
        "references": rows,
        "reference_digests": digests,
        "consumed_rules": consumed[:max_hits],
        "stale_references": [],
    }


def git_context(repo_root: str) -> dict[str, str]:
    repo = Path(repo_root) if repo_root else None
    if not repo or not repo.exists():
        return {"head": "", "branch": "", "status": "missing_repo"}

    def run(*args: str) -> str:
        result = subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""

    inside = run("rev-parse", "--is-inside-work-tree")
    return {
        "head": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "status": "ready" if inside == "true" else "not_git",
    }


def requirement_text(path: Path) -> str:
    if path.suffix.lower() == ".json":
        return json.dumps(load_json(path), ensure_ascii=False)
    return path.read_text(encoding="utf-8", errors="ignore")


def requirement_contracts(text: str) -> list[str]:
    contracts: list[str] = []
    for contract in [*HTTP_METHOD_ROUTE.findall(text), *BACKTICK_ROUTE.findall(text)]:
        if contract.lower().endswith(tuple(SOURCE_SUFFIXES)) or contract in contracts:
            continue
        contracts.append(contract)
    return contracts


def query_terms(text: str) -> list[str]:
    quoted = re.findall(r"[`'\"]([^`'\"]{3,120})[`'\"]", text)
    identifiers = re.findall(r"(?:/[A-Za-z0-9_{}.-]+){2,}|[A-Za-z_][A-Za-z0-9_]{3,}", text)
    chinese = re.findall(r"[\u4e00-\u9fff]{3,12}", text)
    terms: list[str] = []
    for term in [*requirement_contracts(text), *quoted, *identifiers, *chinese]:
        clean = term.strip().lower()
        if clean.startswith("<") or clean in {"/>", ">"} or "=" in clean or not re.search(r"[a-z0-9\u4e00-\u9fff]", clean):
            continue
        if clean and clean not in terms:
            terms.append(clean)
    lower = text.lower()
    for term in sorted(GENERIC_TERMS):
        if term in lower and term not in terms:
            terms.append(term)
    for source, target in WEAK_EQUIVALENTS.items():
        if source in text and target not in terms:
            terms.append(target)
    return terms[:80]


def index_candidates(index: dict[str, Any], terms: list[str], limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in index.get("files", []):
        if not isinstance(item, dict) or not item.get("path"):
            continue
        path = str(item["path"])
        suffix = str(item.get("suffix") or Path(path).suffix).lower()
        if suffix not in SOURCE_SUFFIXES or path.startswith(("docs/", "documentation/")):
            continue
        searchable = json.dumps(item, ensure_ascii=False).lower()
        matched = [term for term in terms if term in searchable]
        if not matched:
            continue
        strong = [term for term in matched if "/" in term or "_" in term or re.search(r"[A-Z]", term, re.I)]
        score = len(matched) * 3 + len(strong) * 4
        candidates.append({"path": str(item["path"]), "index_score": score, "index_terms": matched[:20]})
    candidates.sort(key=lambda item: (item["index_score"], item["path"]), reverse=True)
    return candidates[:limit]


def source_matches(text: str, terms: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    lower = text.lower()
    matched = [term for term in terms if term in lower]
    evidence: list[dict[str, Any]] = []
    lines = text.splitlines()
    for term in matched[:12]:
        for number, line in enumerate(lines, start=1):
            if term in line.lower():
                evidence.append({"term": term, "line": number, "excerpt": line.strip()[:240]})
                break
    return matched, evidence


def location_role(path: str, requirement: str) -> str:
    needles = [path.lower(), Path(path).name.lower(), Path(path).parent.as_posix().lower()]
    for line in requirement.splitlines():
        lower = line.lower()
        if any(needle in lower for needle in needles) and any(term in lower for term in ["reference only", "read only", "reference", "参考", "不作为", "不是本次", "诊断"]):
            return "reference_only"
    return "modify_candidate"


def is_strong(term: str) -> bool:
    if term in GENERIC_TERMS:
        return False
    return bool("/" in term or "_" in term or re.search(r"\d{3,}", term) or (term.isascii() and len(term) >= 8))


def build(repo: Path, index_path: Path, requirement_path: Path, limit: int = 30) -> dict[str, Any]:
    index = load_json(index_path)
    requirement = requirement_text(requirement_path)
    terms = query_terms(requirement)
    candidates = index_candidates(index, terms, limit)
    confirmed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    source_digests: dict[str, str] = {}
    for candidate in candidates:
        relative = candidate["path"]
        path = repo / relative
        if not path.is_file():
            rejected.append({**candidate, "reason": "indexed path does not exist in repository"})
            continue
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="ignore")
        matched, evidence = source_matches(text, terms)
        strong = [term for term in matched if is_strong(term)]
        matched_symbols = [term for term in strong if not term.startswith("/")]
        source_digests[relative] = digest_bytes(raw)
        if len(strong) >= 2 and len(matched) >= 2:
            confirmed.append({
                **candidate,
                "matched_requirement_terms": matched[:20],
                "matched_contract_terms": [term for term in matched if term.startswith("/")],
                "matched_symbols": matched_symbols[:12],
                "symbol": matched_symbols[0] if matched_symbols else "",
                "strong_terms": strong[:12],
                "evidence_chain": evidence,
                "source_digest": source_digests[relative],
                "confidence": "high" if len(strong) >= 2 or len(matched) >= 4 else "medium",
                "role": location_role(relative, requirement),
            })
        else:
            rejected.append({
                **candidate,
                "matched_requirement_terms": matched[:20],
                "reason": "source lacks a requirement-specific symbol, API, protocol id, or multi-signal call-chain match",
            })
    confirmed.sort(key=lambda item: (item["confidence"] == "high", len(item["matched_requirement_terms"]), item["index_score"]), reverse=True)
    modify_candidates = [item for item in confirmed if item.get("role") == "modify_candidate"]
    matched_contract_terms = {
        term.lower()
        for item in confirmed
        if item.get("role") == "modify_candidate"
        for term in item.get("matched_contract_terms", [])
        if term.startswith("/")
    }
    confirmed_contracts: list[str] = []
    for contract in requirement_contracts(requirement):
        if contract.lower() not in matched_contract_terms:
            continue
        if contract not in confirmed_contracts:
            confirmed_contracts.append(contract)
    decision = "pass" if modify_candidates else "block"
    return {
        "schema": SCHEMA,
        "project": index.get("project"),
        "repo_root": str(repo),
        "query_terms": terms,
        "candidates": candidates,
        "confirmed_anchors": confirmed,
        "confirmed_contracts": confirmed_contracts,
        "rejected_candidates": rejected,
        "decision": decision,
        "blockers": [] if modify_candidates else [{"source": "source_location_evidence", "message": "no requirement-specific modify candidate was confirmed"}],
        "warnings": [] if candidates else [{"source": "code_index", "message": "no indexed candidate matched the requirement"}],
        "input_digests": {
            index_path.name: digest_bytes(index_path.read_bytes()),
            requirement_path.name: digest_bytes(requirement_path.read_bytes()),
            **source_digests,
        },
    }


def build_evidence_bundle(source_location: dict[str, Any], max_anchors: int = 12, max_rejected: int = 12, overlay: dict[str, Any] | None = None) -> dict[str, Any]:
    anchors = [item for item in source_location.get("confirmed_anchors", []) if isinstance(item, dict)][:max_anchors]
    normalized: list[dict[str, Any]] = []
    for item in anchors:
        role = "confirmed_reference" if item.get("role") == "reference_only" else "confirmed_modify"
        normalized.append({
            "path": item.get("path", ""),
            "role": role,
            "confidence": item.get("confidence", ""),
            "symbol": item.get("symbol", ""),
            "matched_contract_terms": item.get("matched_contract_terms", [])[:8],
            "matched_symbols": item.get("matched_symbols", [])[:8],
            "evidence_chain": item.get("evidence_chain", [])[:8],
            "source_digest": item.get("source_digest", ""),
            "index_score": item.get("index_score", 0),
        })
    rejected = [
        {"path": item.get("path", ""), "reason": item.get("reason", "")}
        for item in source_location.get("rejected_candidates", [])
        if isinstance(item, dict) and item.get("path")
    ][:max_rejected]
    modify = [item for item in normalized if item["role"] == "confirmed_modify"]
    overlay = overlay or {}
    return {
        "schema": BUNDLE_SCHEMA,
        "project": source_location.get("project", ""),
        "repo_root": source_location.get("repo_root", ""),
        "decision": "pass" if modify else "block",
        "local_project_binding": {
            "project": source_location.get("project", ""),
            "repo_root": source_location.get("repo_root", ""),
            "git": git_context(str(source_location.get("repo_root", ""))),
            "project_skill_dir": overlay.get("skill_dir", ""),
            "project_skill_loaded": bool(overlay.get("loaded")),
            "project_skill_required": bool(overlay.get("skill_dir")),
            "binding_rule": "Repository-backed design must use the local project skill overlay and the Git branch/head captured with source evidence.",
        },
        "confirmed_anchors": [
            {**item, "role": "reference_only" if item["role"] == "confirmed_reference" else "modify_candidate"}
            for item in normalized
        ],
        "anchors": normalized,
        "contracts": source_location.get("confirmed_contracts", [])[:12],
        "rejected_candidates": rejected,
        "overlay_references": overlay.get("references", []),
        "reference_digests": overlay.get("reference_digests", {}),
        "consumed_rules": overlay.get("consumed_rules", []),
        "stale_references": overlay.get("stale_references", []),
        "provenance": {"project_skill_dir": overlay.get("skill_dir", ""), "project_skill_loaded": bool(overlay.get("loaded"))},
        "budgets": {"max_anchors": max_anchors, "max_rejected": max_rejected},
        "blockers": [] if modify else [{"source": "evidence_bundle", "message": "no confirmed modify anchor"}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Confirm requirement-specific code locations against source")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--requirement", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--bundle-out")
    parser.add_argument("--project-skill-dir")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    result = build(Path(args.repo), Path(args.index), Path(args.requirement), args.limit)
    requirement = requirement_text(Path(args.requirement))
    skill_dir = Path(args.project_skill_dir).expanduser() if args.project_skill_dir else None
    overlay = overlay_reference_evidence(skill_dir, requirement)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.bundle_out:
        bundle_out = Path(args.bundle_out)
        bundle_out.parent.mkdir(parents=True, exist_ok=True)
        bundle_out.write_text(json.dumps(build_evidence_bundle(result, overlay=overlay), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
