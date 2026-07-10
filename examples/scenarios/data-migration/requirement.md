# Data Migration Scenario

Business purpose: Make historical order reports consistent with new reporting fields without requiring manual data repair.

Scenario: A release operator runs the migration during deployment, the system backfills existing order rows, and reporting queries read the populated column after deployment.

Entry: Database migration executed by the deployment pipeline.

Req: Add a database migration that backfills a nullable reporting column for existing order rows.

Acceptance criteria:

- The migration is reversible or has a documented rollback path.
- Synthetic test data covers before and after states.
- Data security and performance evidence are attached before release.
