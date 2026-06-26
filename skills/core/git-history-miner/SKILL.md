---
name: git-history-miner
description: Mine generic Git history signals for a source repository. Use when reverse-engineering recent change themes, hotspot files, hotspot directories, and evolution hints without exposing author emails or private remote metadata.
---

# Git History Miner

Use this skill during project understanding to identify recent change themes and hotspots without exposing private author metadata.

## Position

```text
repository-analyzer
-> git-history-miner
-> project-baseline-reverser / project-understanding-runner
-> risk and hotspot review
```

## Rules

- Mine generic signals such as recent themes, hotspot files, hotspot directories, and change frequency.
- Do not output author emails, private remotes, branch secrets, or proprietary ticket URLs.
- Treat shallow, empty, or non-Git repositories as limited evidence with warnings.
- Do not rewrite history, fetch remotes, or mutate the repository.
- Use history signals as risk hints, not as proof of current ownership or correctness.

## Command

```bash
python3 scripts/git_history.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/git_history.json
```

## Output

The output uses schema `codex-git-history-mining-v1`.

The artifact reports recent commit themes, hotspot paths, history limitations, warnings, and privacy-safe metadata.
