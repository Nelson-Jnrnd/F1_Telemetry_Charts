# SPEC-003 UX-007 Responsive Evidence

> This report is derived documentation. SPEC-003 remains authoritative.

_Verified: 2026-08-03._

## Scope

Verify SPEC-003 UX-007 against the current local UI with the canonical cached
2023 Bahrain Grand Prix Race Analysis loaded and a generated Lap Time Delta
chart open. The test covers the application shell, chart surface, and chart
options detail panel.

## Result

UX-007 passes. Desktop and tablet layouts remain usable without horizontal
overflow or visible overlap. At constrained widths, the chart options panel
stacks below the chart instead of competing for horizontal space. A supplemental
mobile-width check also passes.

## Evidence

| Viewport | Document width | Chart | Chart options | Result |
| --- | --- | --- | --- | --- |
| 1440x900 desktop | client 1440 px; scroll 1440 px | 700x393.75 px at x=322 | 360x714 px at x=1039 beside chart | Pass |
| 768x1024 tablet | client 753 px; scroll 753 px | 685x384.44 px ending at y=1257.44 | 687x903 px starting at y=1274.44 below chart | Pass |
| 390x844 mobile | client 375 px; scroll 375 px | 307x171.81 px ending at y=1092.81 | 309x1411 px starting at y=1109.81 below chart | Pass |

The reduced client widths at tablet and mobile sizes reflect the vertical
scrollbar. In each case, `scrollWidth` equals `clientWidth`, proving there is no
document-level horizontal overflow. Rectangle checks that account for clipped
scroll containers found zero simultaneously visible overlaps among buttons,
inputs, selects, textareas, and chart images at all three widths. The browser
console reported no warnings or errors.

## Screenshots

- [Desktop 1440x900](assets/SPEC-003/ux-007-desktop-1440x900.png)
- [Tablet 768x1024](assets/SPEC-003/ux-007-tablet-768x1024.png)
- [Mobile 390x844](assets/SPEC-003/ux-007-mobile-390x844.png)

## Verification boundary

This evidence closes UX-007 and supports NFR-002 layout stability. It does not
by itself close the separate keyboard-accessibility, package-scale, observation
dialog, or chart-lightbox interaction checks.
