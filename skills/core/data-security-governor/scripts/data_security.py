#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-data-security-review-v1"
SENSITIVE_TERMS = ["pii", "personal", "phone", "email", "address", "id card", "payment", "secret", "token", "tenant", "permission", "export", "log", "手机号", "身份证", "支付", "密钥", "租户", "权限", "导出", "日志"]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def text_of(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def design_review(*docs: dict[str, Any]) -> dict[str, Any]:
    text = text_of(*docs)
    signals = [term for term in SENSITIVE_TERMS if term in text]
    findings: list[dict[str, str]] = []
    controls: list[dict[str, str]] = []
    if signals:
        controls.extend([
            {"control": "permission_boundary", "requirement": "backend-authoritative permission or data-scope check"},
            {"control": "log_redaction", "requirement": "do not log secrets or sensitive personal data"},
            {"control": "test_negative_case", "requirement": "include unauthorized/other-tenant negative test where applicable"},
        ])
    if any(term in signals for term in ["payment", "支付"]):
        controls.append({"control": "payment_data_minimization", "requirement": "store and expose only required payment metadata"})
    if any(term in signals for term in ["export", "导出"]):
        controls.append({"control": "export_scope", "requirement": "validate export permission, filters, row limits, and audit trail"})
    if signals and "permission_model" not in text and "permission" in signals:
        findings.append({"severity": "high", "status": "open", "message": "permission-sensitive design needs explicit permission model"})
    decision = "ready" if signals else "pass"
    release_blockers = [item["message"] for item in findings if item["severity"] in {"blocker", "high"}]
    return {
        "schema": SCHEMA,
        "decision": decision,
        "review_status": "needs_review" if signals else "no_sensitive_signal",
        "sensitive_signals": sorted(set(signals)),
        "controls_required": controls,
        "findings": findings,
        "blockers": [],
        "release_blockers": release_blockers,
        "warnings": [] if signals else [{"source": "data_security", "message": "no sensitive data signals detected"}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate data security review")
    parser.add_argument("cmd", choices=["design"])
    parser.add_argument("--spec", required=True)
    parser.add_argument("--technical-design", required=True)
    parser.add_argument("--architecture-design", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = design_review(load_json(Path(args.spec)), load_json(Path(args.technical_design)), load_json(Path(args.architecture_design)))
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] in {"pass", "ready"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
