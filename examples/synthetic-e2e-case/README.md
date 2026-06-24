# Synthetic End-to-End Case

This example is intentionally generic and safe for open-source publication.

Scenario:

- A user needs an order export page.
- Only an admin can export filtered results.
- The export must include order id and status.

Suggested flow:

```bash
python3 skills/core/requirement-document-ingestor/scripts/ingest_requirement.py --input examples/synthetic-e2e-case/requirement.md --doc-id REQ-SYN-001 --out-dir /tmp/codex-synthetic
python3 skills/core/spec-governor/scripts/spec_governor.py normalize --doc-id REQ-SYN-001 --title "Order export" --input /tmp/codex-synthetic/requirement.normalized.txt --out /tmp/codex-synthetic/spec.json
python3 skills/core/technical-design-governor/scripts/technical_design.py --spec /tmp/codex-synthetic/spec.json --out /tmp/codex-synthetic/technical_design.json
python3 skills/core/architecture-design-governor/scripts/architecture_design.py --spec /tmp/codex-synthetic/spec.json --technical-design /tmp/codex-synthetic/technical_design.json --out /tmp/codex-synthetic/architecture_design.json
python3 skills/core/test-design-governor/scripts/test_design.py render --spec /tmp/codex-synthetic/spec.json --technical-design /tmp/codex-synthetic/technical_design.json --architecture-design /tmp/codex-synthetic/architecture_design.json --out /tmp/codex-synthetic/test_design.json
python3 skills/core/delivery-runner/scripts/delivery_runner.py inspect --artifact-dir /tmp/codex-synthetic
```
