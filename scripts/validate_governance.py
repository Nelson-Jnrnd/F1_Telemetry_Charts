#!/usr/bin/env python3
"""Validate that required governance/workflow files exist.

Project-agnostic. Exits non-zero if any required file is missing (blocking).
Prints warnings for weaker signals but does not fail on them.

Usage: python scripts/validate_governance.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that must exist for the governance workflow to function.
REQUIRED_FILES = [
    "CLAUDE.md",
    "AGENTS.md",
    "docs/SPEC_INDEX.md",
    "docs/specs/SPEC_TEMPLATE.md",
    "docs/workflow/AGENT_WORKFLOW.md",
    "docs/workflow/DEFINITION_OF_READY.md",
    "docs/workflow/DEFINITION_OF_DONE.md",
    "docs/workflow/DOCUMENTATION_AUTHORITY.md",
    "docs/workflow/HUMAN_REVIEW_GUIDE.md",
    "docs/workflow/AGENT_HANDOFF_TEMPLATE.md",
    "docs/workflow/GITHUB_PROJECT_SETUP.md",
    "docs/workflow/REPOSITORY_ADMIN_SETUP.md",
    ".github/ISSUE_TEMPLATE/feature_spec.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/agent_task.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".claude/commands/status.md",
    ".claude/commands/spec-report.md",
    ".claude/commands/drift-check.md",
    ".claude/commands/handoff.md",
    "scripts/validate_governance.py",
    "scripts/validate_specs.py",
    "scripts/validate_drift.py",
    ".github/workflows/governance.yml",
]

# Directories that should exist (spec lifecycle folders).
REQUIRED_DIRS = [
    "docs/specs/active",
    "docs/specs/approved",
    "docs/specs/implemented",
    "docs/specs/archived",
]

# Nice-to-have files; missing ones are warnings, not failures.
RECOMMENDED_FILES = [
    "README.md",
    "CONTRIBUTING.md",
]


def main() -> int:
    blocking: list[str] = []
    warnings: list[str] = []

    for rel in REQUIRED_FILES:
        if not (REPO_ROOT / rel).is_file():
            blocking.append(f"Missing required file: {rel}")

    for rel in REQUIRED_DIRS:
        if not (REPO_ROOT / rel).is_dir():
            blocking.append(f"Missing required directory: {rel}")

    for rel in RECOMMENDED_FILES:
        if not (REPO_ROOT / rel).is_file():
            warnings.append(f"Missing recommended file: {rel}")

    print("== Governance validation ==")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")

    if blocking:
        print("\nBlocking issues:")
        for b in blocking:
            print(f"  - {b}")
        print(f"\nFAILED: {len(blocking)} blocking issue(s).")
        return 1

    print("\nOK: all required governance files present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
