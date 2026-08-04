# SPEC-002/003/004 Closeout Evidence

> This report is derived documentation. The approved specs remain authoritative.

_Verified: 2026-08-04._

## Result

The previously recorded package-inspection, performance, scale, Markdown
safety, lightbox, keyboard, and Review interaction gaps are closed. Formal spec
lifecycle status remains `In Implementation` because no delivery PR or merge is
recorded.

## Automated evidence

| Check | Result |
| --- | --- |
| Preview reader tests | 8 passed |
| Full Python discovery | 102 passed in 24.538 seconds on the final run |
| Frontend typecheck | Passed |
| Frontend production build | Passed; Vite emitted the existing bundle-size advisory |
| Representative package benchmark | 20 charts, 50 observations, healthy, 0.0813 seconds against a 3-second limit |

The reproducible fixture and benchmark live in
`scripts/benchmark_package_preview.py`. It clones the checked-in Bahrain Race
Analysis/package, produces valid duplicated chart assets and observation
evidence, refuses to overwrite a supplied output directory, and otherwise
cleans its temporary directory.

## Browser evidence

The in-app current-Chromium session used the generated representative fixture.

| Surface | Evidence | Result |
| --- | --- | --- |
| Export overview | Reported 20 charts, 50 observations, healthy integrity, and draft ready | Pass |
| Desktop chart grid | 20 images at 1440x900; document width equaled viewport width | Pass |
| Mobile chart grid | 20 images at 390x844; 375 px document and viewport widths; largest image 308 px | Pass |
| Mobile draft | 375 px document and viewport widths | Pass |
| Mobile integrity | 44 rows; wide table contained in a 307 px horizontal scroller without document overflow | Pass |
| Export tabs | Arrow-key navigation moved selection between Radix tabs | Pass |
| Chart lightbox | Opened at viewport-fit size, preserved the image, and closed with Escape or backdrop click | Pass |
| Draft modes | Rendered mode produced Markdown structure; Raw mode displayed literal source | Pass |
| Markdown safety | Injected script and image event-handler HTML created no script/image nodes and did not execute | Pass |
| Integrity details | Selecting a finding showed labeled area, path, and message fields | Pass |
| Review cancel | Typed edit was discarded; the review-file hash remained unchanged | Pass |
| Review save | Persisted edited status/text and regenerated the draft; action controls have observation-specific accessible names | Pass |
| Session lifecycle | Loaded state and session details were visible; Add exposed editable data-source inputs; the editor exposed Load/Remove; removing the session with 20 dependent charts opened the native warning confirmation | Pass |

Existing responsive screenshots for the application shell and chart-options
layout remain in `docs/reports/SPEC-003-UX-007-responsive-evidence.md`.

## Verification boundary

This closes the evidence gaps named in the 2026-08-03 status/spec/drift
reports. It does not satisfy the separate delivery lifecycle gate: a related PR
must still be recorded and merged before the specs can move to `Implemented`.
