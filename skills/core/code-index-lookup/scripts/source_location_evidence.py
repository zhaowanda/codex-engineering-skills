#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-source-location-evidence-v1"
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Confirm requirement-specific code locations against source")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--requirement", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    result = build(Path(args.repo), Path(args.index), Path(args.requirement), args.limit)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
