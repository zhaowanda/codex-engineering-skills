# Release Readiness Prompt

Scenario: a user asks whether a change can be released.

Run release readiness as a gate decision.

Required behavior:

- Validate implementation completion, write guard, scope boundary, code review, test evidence, frontend acceptance when UI changed, configuration, environment promotion, UAT, release change, rollback, post-release observation, dependency/license, and version release evidence.
- Classify release risk and require explicit approval for high-risk or critical changes.
- Stop release if any required artifact is missing or blocking.
- Produce a go, conditional_go, or no_go decision.

Stop conditions:

- Required evidence is missing.
- Rollback is unclear.
- Release notes or changelog are required but missing.
- Privacy or skill health checks fail.

Evidence:

- Release gate output.
- Risk classification.
- Rollback plan.
- Post-release checks.
