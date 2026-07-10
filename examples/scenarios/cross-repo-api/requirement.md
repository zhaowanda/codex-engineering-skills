# Cross-Repo API Scenario

Business purpose: Let the frontend display order status from the backend source of truth without breaking existing API consumers.

Scenario: Frontend opens the order detail page, calls the backend order API, receives the new status field when available, and keeps rendering correctly when old responses omit it.

Entry: Frontend order detail page calling the backend order API.

Req: Add a backward-compatible order status field to an API consumed by a separate frontend repository.

Acceptance criteria:

- The API response adds the new field without removing existing fields.
- The frontend consumer keeps working when the field is absent.
- Contract and traceability evidence identify producer and consumer responsibilities.
