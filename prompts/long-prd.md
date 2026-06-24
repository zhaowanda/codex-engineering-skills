# Long PRD Prompt

Scenario: a user provides a long PRD, PDF export, or copied online document.

Use requirement ingestion first. Normalize the PRD into machine-readable artifacts and human-readable summaries before implementation.

Required behavior:

- Ingest and normalize the document.
- Extract scope boundary, roles, rules, acceptance criteria, open questions, configuration, data security, performance, and release constraints.
- Produce technical design and architecture design with option comparison, flows, data flow, API or UI behavior, rollback, and observability.
- Stop before implementation until design review, test design, traceability, risk, Git readiness, and edit readiness pass.
- Keep evidence artifacts separate from human-readable documents.

Stop conditions:

- Product rules conflict.
- Acceptance criteria are not testable.
- Required configuration or environment evidence is missing.
- Cross-repository boundary is unclear.

Evidence:

- Attach normalized requirement, spec, design, test, traceability, and risk artifacts.
- Summarize remaining gaps.
