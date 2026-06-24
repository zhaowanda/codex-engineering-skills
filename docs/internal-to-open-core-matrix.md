# Internal To Open-Core Matrix

This matrix defines how to extract an internal engineering skill system into the open-source core.

## Directly Extract After Path Configuration

These components are mostly generic but must remove absolute paths and company-specific defaults:

| Component | Open-Core Name | Required Changes |
|---|---|---|
| delivery state governor | delivery-state-governor | Replace fixed paths with config/env |
| git worktree governor | git-worktree-governor | Replace project registry dependency with adapter |
| edit readiness governor | edit-readiness-governor | Replace docs repo layout constants with config |
| workspace write guard | workspace-write-guard | Keep generic; remove company naming |
| frontend acceptance runner | frontend-acceptance-runner | Keep generic Chrome DevTools evidence contract |
| code design quality reviewer | code-design-quality-reviewer | Keep generic diff heuristics; remove private examples |
| design architecture reviewer | design-architecture-reviewer | Keep generic scoring and gates |

## Extract With Template Rewrite

These contain useful structure but must be rewritten as neutral templates:

| Component | Open-Core Treatment |
|---|---|
| company engineering entrypoint | Rename to engineering-entrypoint; remove company project routing |
| company delivery runner | Rename to delivery-runner; inject registry and knowledge provider |
| company workflow orchestrator | Rename to workflow-orchestrator; remove internal semantic map |
| company test governor | Rename to test-governor; project strategies become examples |
| delivery docs governor | Keep lifecycle model; make repo layout configurable |
| release evidence binder | Keep gate model; remove organization-specific release terms |
| requirement document ingestor | Keep generic ingestion; remove internal doc conventions |

## Keep Private

Do not publish:

| Internal Asset | Reason |
|---|---|
| project skills | Contain real project boundaries and code facts |
| generated code indexes | Derived from private source code |
| baseline docs | Derived from private source code and history |
| contract-patterns.json | Encodes internal architecture and business contracts |
| semantic-map.yaml | Encodes business vocabulary |
| real golden cases | May reveal workflows, systems, and customer context |
| company PPT and delivery artifacts | Internal communication and examples |

## Rewrite As Synthetic Examples

Use fake but realistic examples:

- `example-frontend`
- `example-api`
- `example-auth`
- `example-report`
- `example-payment-adapter`

Example business cases should be generic:

- field display bugfix
- report export field addition
- role permission change
- payment adapter migration
- message queue topic configuration
- frontend table/filter change

## Release Rule

Every migrated file must pass:

```bash
python3 scripts/privacy_scan.py --root . --patterns config/private-patterns.example.yaml
python3 -m pytest tests
```

