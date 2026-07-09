#!/usr/bin/env python3
"""Detect documentation drift and conflicting specs.

Checks (project-agnostic):
  - Duplicate spec IDs across spec files.
  - Duplicate requirement IDs within a single spec.
  - Approved/Implemented specs modified without an amendment marker.
  - Requirement IDs introduced outside specs (reports / README).
  - Implemented specs without a PR reference (where detectable).

Blocking issues exit non-zero; weaker signals are warnings.
Dependency-free.

Usage: python scripts/validate_drift.py
"""
from __future__ import annotations

import re
import subprocess
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

# Files that are derived and must NOT introduce requirement IDs.
DERIVED_GLOBS = [
    "docs/reports/PROJECT_STATUS.md",
    "docs/reports/SPEC_REPORT.md",
    "docs/reports/DRIFT_REPORT.md",
    "README.md",
]

REQ_ID_RE = re.compile(r"\b(?:REQ|NFR|SEC|UX|DATA|API)-\d{3,}\b")
SPEC_ID_RE = re.compile(r"^SPEC-\d{3,}$", flags=re.MULTILINE)
FRONTMATTER_SPEC_ID_RE = re.compile(r"^spec_id:\s*(SPEC-\d{3,})\s*$", flags=re.MULTILINE)
FRONTMATTER_STATUS_RE = re.compile(r"^status:\s*(.+?)\s*$", flags=re.MULTILINE)


def iter_specs() -> list[Path]:
    specs: list[Path] = []
    for d in SPEC_DIRS:
        base = REPO_ROOT / d
        if base.is_dir():
            for p in base.glob("*.md"):
                if p.name != TEMPLATE_NAME:
                    specs.append(p)
    return sorted(specs)


def git_tracked(rel: str) -> bool:
    try:
        r = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", rel],
            capture_output=True,
            text=True,
        )
        return r.returncode == 0
    except Exception:
        return False


def main() -> int:
    blocking: list[str] = []
    warnings: list[str] = []

    specs = iter_specs()

    # 1. Duplicate spec IDs.
    seen_spec_ids: dict[str, str] = {}
    for path in specs:
        text = path.read_text(encoding="utf-8")
        m = FRONTMATTER_SPEC_ID_RE.search(text)
        if not m:
            continue
        sid = m.group(1)
        rel = str(path.relative_to(REPO_ROOT))
        if sid in seen_spec_ids:
            blocking.append(
                f"Duplicate spec_id {sid} in {rel} and {seen_spec_ids[sid]}"
            )
        else:
            seen_spec_ids[sid] = rel

    # 2. Duplicate requirement IDs within a single spec.
    for path in specs:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(REPO_ROOT))
        # Count requirement IDs that appear as a heading definition, e.g.
        # "### REQ-001:". Reuse of the same ID as a definition is a conflict.
        defined = re.findall(
            r"^#{1,6}\s+((?:REQ|NFR|SEC|UX|DATA|API)-\d{3,})\b",
            text,
            flags=re.MULTILINE,
        )
        counts: dict[str, int] = {}
        for rid in defined:
            counts[rid] = counts.get(rid, 0) + 1
        for rid, n in counts.items():
            if n > 1:
                blocking.append(
                    f"Duplicate requirement definition {rid} ({n}x) in {rel}"
                )

    # 3. Approved/Implemented specs modified without amendment marker.
    for path in specs:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(REPO_ROOT))
        status_m = FRONTMATTER_STATUS_RE.search(text)
        status = status_m.group(1).strip() if status_m else ""
        if status in {"Approved", "Implemented", "In Implementation"}:
            # Heuristic: an amendment entry (AMEND-XXX) should exist if the spec
            # has been changed after approval. We can only detect the *absence*
            # of any amendment section content and warn.
            has_amendment = re.search(r"\bAMEND-\d{3,}\b", text) is not None
            if not has_amendment and git_tracked(rel):
                warnings.append(
                    f"{rel} is '{status}' with no amendment entries; behavioral "
                    "changes after approval require a Spec Amendments entry."
                )

    # 4. Requirement IDs introduced outside specs (derived docs).
    for rel in DERIVED_GLOBS:
        p = REPO_ROOT / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8")
        # Strip lines that clearly reference the ID scheme rather than define
        # requirements (the drift rules mention the ID names themselves).
        found = set(REQ_ID_RE.findall(text))
        if found:
            warnings.append(
                f"{rel} contains requirement-shaped IDs {sorted(found)}; derived "
                "docs must not introduce requirements. Confirm these are only "
                "references, not definitions."
            )

    # 5. Implemented specs without a PR reference.
    for path in specs:
        text = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(REPO_ROOT))
        status_m = FRONTMATTER_STATUS_RE.search(text)
        status = status_m.group(1).strip() if status_m else ""
        if status == "Implemented":
            prs_m = re.search(r"^related_prs:\s*(.+)$", text, flags=re.MULTILINE)
            raw = prs_m.group(1).strip() if prs_m else "[]"
            if raw in {"", "[]"}:
                blocking.append(
                    f"{rel} is 'Implemented' but has no related_prs reference."
                )

    print("== Drift validation ==")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")
    if blocking:
        print("\nBlocking issues:")
        for b in blocking:
            print(f"  - {b}")
        print(f"\nFAILED: {len(blocking)} blocking issue(s).")
        print("If this is a genuine conflict between authoritative documents, "
              "stop and ask the human to decide.")
        return 1

    if not specs:
        print("\nNo specs yet; nothing to drift. OK.")
    else:
        print("\nOK: no blocking drift detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
