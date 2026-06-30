#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


SCHEMA = "codex-ci-template-render-v1"
PY_COMPILE = """python3 - <<'PY'
from pathlib import Path
import py_compile
paths = [p for p in Path('.').rglob('*.py') if '.git' not in p.parts and '__pycache__' not in p.parts]
for path in paths:
    py_compile.compile(str(path), doraise=True)
print(f"compiled {len(paths)} python files")
PY"""

RUN_TESTS = """python3 - <<'PY'
from pathlib import Path
import subprocess
tests = sorted(Path('tests').glob('test_*.py'))
for test in tests:
    subprocess.run(['python3', str(test)], check=True)
print(f"ran {len(tests)} test files")
PY"""

PRIVACY_SCAN = "python3 scripts/privacy_scan.py --root . --patterns config/private-patterns.example.yaml"
SKILL_HEALTH = "python3 skills/core/skill-health/scripts/skill_health.py --root ."


def github_template() -> str:
    return f"""name: validate

on:
  pull_request:
  push:
    branches:
      - main
      - master

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Compile Python
        run: |
{indent(PY_COMPILE, 10)}
      - name: Run tests
        run: |
{indent(RUN_TESTS, 10)}
      - name: Privacy scan
        run: {PRIVACY_SCAN}
      - name: Skill health
        run: {SKILL_HEALTH}
"""


def gitlab_template() -> str:
    return f"""stages:
  - validate

validate:
  image: python:3.11
  stage: validate
  script:
    - |
{indent(PY_COMPILE, 6)}
    - |
{indent(RUN_TESTS, 6)}
    - {PRIVACY_SCAN}
    - {SKILL_HEALTH}
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_COMMIT_BRANCH == "main"'
    - if: '$CI_COMMIT_BRANCH == "master"'
"""


def indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def render(provider: str) -> str:
    if provider == "github":
        return github_template()
    if provider == "gitlab":
        return gitlab_template()
    raise ValueError("provider must be github or gitlab")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render CI template")
    parser.add_argument("--provider", choices=["github", "gitlab"], required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    content = render(args.provider)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
