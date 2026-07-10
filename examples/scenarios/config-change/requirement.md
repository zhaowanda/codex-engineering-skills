# Configuration Change Scenario

Business purpose: Let release engineers route generated evidence into the correct workspace path without moving files manually.

Scenario: Release engineer runs the evidence generation command with an output directory argument, the system creates the directory when safe, and writes release evidence there.

Entry: Evidence generation CLI command with output directory argument.

Req: Add a configurable output directory for generated release evidence.

Acceptance criteria:

- The output directory can be set by command argument.
- Missing directories are created safely.
- The configuration change is reflected in validation evidence.
