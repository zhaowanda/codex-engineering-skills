# Code Review Scenario

Business purpose: Prevent unsafe merge of a change that affects API behavior, authorization, and user-visible export UI.

Scenario: Reviewer opens the submitted diff, inspects API, permission, and frontend changes, and records blocking findings before approval.

Entry: Code review gate executed on the submitted diff.

Req: Review an existing diff that changes API behavior, permission checks, and frontend export UI.

Acceptance criteria:

- Diff impact identifies API, permission, frontend, and test evidence needs.
- Code design review reports active blockers before approval.
- Test and CI evidence are bound before merge or release.
