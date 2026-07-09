#!/usr/bin/env python3
"""Validate specification files.

Checks each spec under docs/specs/{active,approved,implemented,archived} for:
  - YAML frontmatter block
  - spec_id, status, title
  - required sections
  - at least one requirement ID (REQ/NFR/SEC/UX/DATA/API)
  - acceptance criteria present
  - a verification matrix

The SPEC_TEMPLATE.md file is skipped (it is a template, not a real spec).
Dependency-free: does not require PyYAML.

Blocking failures exit non-zero. Weaker signals are warnings.

Usage: python scripts/validate_specs.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPEC_DIRS = [
    "docs/specs/active",
    "docs/specs/approved",
    "docs/specs/implemented",
    "docs/specs/archived",
]
TEMPLATE_NAME = "SPEC_TEMPLATE.md"

ALLOWED_STATUSES = {
    "Draft",
    "In Review",
    "Approved",
    "In Implementation",
    "Implemented",
    "Superseded",
    "Archived",
    "Rejected",
}

REQUIRED_FRONTMATTER_KEYS = ["doc_type", "spec_id", "title", "status"]

REQUIRED_SECTIONS = [
    "Summary",
    "Context",
    "Problem statement",
    "Goals",
    "Non-goals",
    "Functional requirements",
    "Acceptance criteria",
    "Verification matrix",
    "Test plan",
    "Rollback plan",
    "Traceability table",
]

REQ_ID_RE = re.compile(r"\b(REQ|NFR|SEC|UX|DATA|API)-\d{3,}\b")
SPEC_ID_RE = re.compile(r"^SPEC-\d{3,}$")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """Very small frontmatter parser. Returns key->raw value (strings only)."""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    block = parts[1]
    data: dict[str, str] = {}
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        # Only treat top-level keys (no leading indentation) as fields.
        if line[0] in " \t-":
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip()
    return data


def check_spec(path: Path) -> tuple[list[str], list[str]]:
    blocking: list[str] = []
    warnings: list[str] = []
    rel = path.relative_to(REPO_ROOT)
    text = path.read_text(encoding="utf-8")

    fm = parse_frontmatter(text)
    if fm is None:
        blocking.append(f"{rel}: missing YAML frontmatter block")
        return blocking, warnings

    for key in REQUIRED_FRONTMATTER_KEYS:
        if not fm.get(key):
            blocking.append(f"{rel}: frontmatter missing or empty '{key}'")

    spec_id = fm.get("spec_id", "")
    if spec_id and not SPEC_ID_RE.match(spec_id):
        blocking.append(
            f"{rel}: spec_id '{spec_id}' does not match SPEC-XXX format"
        )

    status = fm.get("status", "")
    if status and status not in ALLOWED_STATUSES:
        blocking.append(
            f"{rel}: status '{status}' is not one of {sorted(ALLOWED_STATUSES)}"
        )

    # Required sections (markdown headings).
    headings = set(
        m.group(1).strip().rstrip(":").lower()
        for m in re.finditer(r"^#{1,6}\s+(.+)$", text, flags=re.MULTILINE)
    )
    for section in REQUIRED_SECTIONS:
        if section.lower() not in headings:
            blocking.append(f"{rel}: missing required section '{section}'")

    # At least one requirement ID.
    if not REQ_ID_RE.search(text):
        blocking.append(
            f"{rel}: no requirement IDs found (expected REQ/NFR/SEC/UX/DATA/API-XXX)"
        )

    # Acceptance criteria present as text.
    if "acceptance criteria" not in text.lower():
        blocking.append(f"{rel}: no 'Acceptance criteria' content found")

    # Verification matrix table (a markdown table under the section).
    if "verification matrix" in headings:
        after = text.lower().split("verification matrix", 1)[1]
        if "|" not in after.split("##", 1)[0]:
            warnings.append(f"{rel}: verification matrix section has no table rows")

    return blocking, warnings


def main() -> int:
    spec_files: list[Path] = []
    for d in SPEC_DIRS:
        base = REPO_ROOT / d
        if base.is_dir():
            for p in base.glob("*.md"):
                if p.name != TEMPLATE_NAME:
                    spec_files.append(p)

    print("== Spec validation ==")

    if not spec_files:
        print("\nNo specs found yet (nothing to validate). OK.")
        return 0

    all_blocking: list[str] = []
    all_warnings: list[str] = []
    for path in sorted(spec_files):
        b, w = check_spec(path)
        all_blocking.extend(b)
        all_warnings.extend(w)

    print(f"\nChecked {len(spec_files)} spec file(s).")

    if all_warnings:
        print("\nWarnings:")
        for w in all_warnings:
            print(f"  - {w}")

    if all_blocking:
        print("\nBlocking issues:")
        for b in all_blocking:
            print(f"  - {b}")
        print(f"\nFAILED: {len(all_blocking)} blocking issue(s).")
        return 1

    print("\nOK: all specs valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
