# GitHub Project Setup (Recommended)

A simple GitHub Project board helps you track work from your phone without
opening files. This is a **recommendation** — nothing here is enforced by code,
and you can set it up whenever you like. Keep it simple; do not build a
corporate dashboard.

## Create the project

1. On GitHub, go to the repository → **Projects** → **New project** → **Board**.
2. Name it e.g. "paleo-map".

## Recommended fields

Add these custom fields to items:

| Field | Type | Purpose |
| ----- | ---- | ------- |
| **Phase** | Single select | Lifecycle phase (see values below). |
| **Spec ID** | Text | The governing `SPEC-XXX`. |
| **Priority** | Single select | Low / Medium / High. |
| **Risk** | Single select | Low / Medium / High. |
| **Blocked** | Checkbox | Whether the item is blocked. |
| **Blocked reason** | Text | Why it is blocked. |
| **PR** | Text / URL | Linked pull request. |
| **Verification status** | Single select | Not started / In progress / Passed / Failed. |

Suggested **Phase** values (mirror the workflow lifecycle): `Intake`,
`Spec draft`, `Spec review`, `Approved`, `In implementation`, `Verification`,
`In review`, `Done`.

## Recommended views

- **Current work** — items in `In implementation` or `Verification`.
- **Specs to review** — items in `Spec review`.
- **Ready to implement** — items in `Approved`.
- **Blocked** — items where `Blocked` is checked.
- **Done** — items in `Done`.

## Keeping it lightweight

- One board is enough. Do not add fields you will not read.
- The spec files remain the source of truth; the board is just a view.
- `/status` and `/spec-report` give you the same information from Claude Code.
