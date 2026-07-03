# Cross-Repo API Scenario

Add a backward-compatible order status field to an API consumed by a separate frontend repository.

Acceptance criteria:

- The API response adds the new field without removing existing fields.
- The frontend consumer keeps working when the field is absent.
- Contract and traceability evidence identify producer and consumer responsibilities.
