# Architecture

## Concept

The framework turns an AI coding assistant into a gated engineering workflow participant.

```text
requirement input
-> normalized spec
-> technical design
-> architecture design
-> delivery plan
-> Git baseline and feature branch
-> edit permit
-> implementation in allowed scope
-> design/code/security/performance review
-> tests and frontend acceptance
-> release evidence
-> post-change learning
```

## Key Design Decisions

- Human docs and machine JSON are separate.
- Skills provide workflow knowledge; scripts provide deterministic gates.
- Project-specific knowledge is an overlay, not part of the open core.
- Source-code indexes are generated assets and must stay private by default.
- The platform command should answer: current stage, blockers, next command, and whether coding/release is allowed.
- Skills declare `category`, `maturity`, `stage`, and `gate` in frontmatter so orchestration and health checks can distinguish expert gates from helpers and templates.
- Workflow profiles are executable contracts: they declare required skills, expected artifacts, required gate artifacts, accepted decisions, and readiness fields that runners can validate.
- Workflow stages are registry-driven so stage order, artifact names, and next commands do not drift across runners.

## Runtime Layers

- Workflow orchestration: `auto-runner`, `project-runner`, `project-understanding-runner`, `delivery-runner`, and synthetic/example runners choose the next safe command.
- Expert gates: requirement, design, delivery-plan, Git/edit, implementation, review, test, and release gates block shallow or unsafe progress.
- Evidence builders: extractors, analyzers, templates, and documentation helpers create structured inputs for gates without claiming expert-gate authority.
- Overlay/runtime: private project knowledge and per-requirement artifacts stay outside open core unless fully synthetic.

## Workflow Registries

- `config/workflow-profiles.example.yaml` defines scenario profiles such as bugfix, frontend change, cross-repo API, data migration, and release readiness.
- Each profile declares `required_gate_artifacts` so orchestration can block missing artifacts, rejected decisions, or failed readiness fields.
- `config/workflow-stages.example.yaml` defines the canonical stage order, artifact filename, next safe command, and whether the stage is required before implementation or release.
- `delivery-runner` reads both registries to report next stage, blockers, and implementation/release readiness.
- `skill-health` validates both registries for schema, missing fields, duplicate stages, and unknown skills.

## Skill Taxonomy

- `workflow-gate`: blocks or allows a delivery stage.
- `release-governor`: blocks or allows release and post-release decisions.
- `reviewer`: advisory review with warnings or blocking findings when applicable.
- `extractor-analyzer`: deterministic repository or artifact analysis.
- `artifact-generator`: creates draft artifacts that still require review.
- `template-runner`: renders templates or orchestrates example workflows.
- `meta-governor`: validates the open-core framework, docs, prompts, packaging, or compatibility.

Maturity values are intentionally distinct from quality claims:

- `expert-gate`: must be a gate, have direct tests, and expose `schema`, `decision`, and `blockers`.
- `advisory-review`: can gate thin artifacts but does not represent final implementation authority.
- `deterministic-helper`: creates evidence or validates repository health with deterministic checks.
- `template`: provides reusable skeletons or renderers.
- `orchestrator`: selects and sequences skills without replacing downstream gates.

## Gate Contract

Gate-like skills must document or emit these fields:

- `schema`
- `decision`
- `blockers`
- `warnings` when non-blocking concerns exist
- `next_action` when a human or agent must continue
- `readiness_gate.implementation_allowed` when the gate controls implementation

## Extension Points

- Project registry adapter.
- Docs repository adapter.
- CI provider templates.
- Browser acceptance provider.
- Semantic knowledge provider.
- Privacy pattern configuration.
