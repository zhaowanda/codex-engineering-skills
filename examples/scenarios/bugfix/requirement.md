# Bugfix Scenario

Fix a validation bug where a generated delivery artifact is marked ready even when required test evidence is missing.

Acceptance criteria:

- The gate blocks missing test evidence.
- The error message identifies the missing evidence.
- Existing passing artifacts remain accepted.
