#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INSTALLER = ROOT / "skills/core/skill-installation-governor/scripts/install_skills.py"


def main() -> int:
    return subprocess.run([sys.executable, str(INSTALLER), "--source", str(ROOT), *sys.argv[1:]], cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
