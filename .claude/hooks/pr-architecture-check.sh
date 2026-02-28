#!/usr/bin/env bash
# Hook: Remind to update CLAUDE.md and ARCHITECTURE.md when creating PRs
# This runs as a pre-commit or PR creation reminder

set -euo pipefail

echo "Reminder: If this PR changes project structure, update CLAUDE.md and ARCHITECTURE.md"
