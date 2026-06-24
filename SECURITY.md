# Security Policy

## Supported Versions

The `main` branch receives security fixes. Tagged releases are supported until the next minor release unless the changelog says otherwise.

## Reporting A Vulnerability

Do not disclose sensitive vulnerabilities, secrets, private data, or exploit details in a public issue. Report privately to the maintainers through the repository owner contact channel or a private advisory if available.

## Response Process

Maintainers triage security reports, confirm impact, prepare a fix, run privacy scan and dependency checks, and publish release notes when needed.

## Private Data And Secrets

Do not commit customer data, organization-specific project names, internal hostnames, private overlays, generated indexes, baseline documents, passwords, tokens, certificates, or local absolute paths.

## Required Checks

Security-sensitive changes should run:

```bash
python3 scripts/privacy_scan.py --root . --patterns config/private-patterns.example.yaml
python3 skills/core/dependency-license-governor/scripts/dependency_license.py --root .
python3 skills/core/data-security-governor/scripts/data_security.py --help
```
