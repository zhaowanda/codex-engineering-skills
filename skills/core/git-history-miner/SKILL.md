---
name: git-history-miner
description: Mine generic Git history signals for a source repository. Use when reverse-engineering recent change themes, hotspot files, hotspot directories, and evolution hints without exposing author emails or private remote metadata.
---

# Git History Miner

## Command

```bash
python3 skills/core/git-history-miner/scripts/git_history.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/git_history.json
```

## Output

The output uses schema `codex-git-history-mining-v1`.
