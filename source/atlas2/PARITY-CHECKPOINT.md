# Local parity checkpoint — batch05

Historical failed result. The descriptor-capacity cause and subsequent synthetic
and native repair evidence are in [TEXTURE-LIFECYCLE.md](TEXTURE-LIFECYCLE.md).

Buildable integration commit: `9088ab4`, separate from preserved prototype
`d553827`. No remote push or release. The pinned installation and original saves
remain protected. Renderer preparation workers remain zero.

## Implemented and tested offline

The CPU baker now uses the V1 parchment material, shared height range and color
formula, interior fills, deterministic interior/cut hatching, near/far context,
ordered composition, normal reveal variants and elevation-shading variants.
Fourteen composite views use 16 texels/native world unit: Area02's 12 views,
Area06 F021 and Area10 F032. The other 588 views remain legacy 8-ppu fallbacks.
The mixed set contains all 16 areas; it is not an all-area visual parity result.

Active wall/outline widths use the V1 screen-space formulas. These are a bounded
indexed overlay, at most 8192 segments in one active view, with visible candidates
cached by viewport cell range and reveal decisions. Runtime drawing does not load
the full V1 triangle arrays. The hatch/context stroke widths remain calibrated to
normalized zoom 9 at each raster LOD. Dynamic icon-footprint hatch masking and
native-equivalent raster antialiasing remain incomplete.

Content validation checked 2907 unique new tile hashes and the 14 line files.
Mixed pack size: 409,413,139 bytes. CPU generation took 7.671 s (Area02), 18.344 s
(Area06 F021) and 34.015 s (Area10 F032). A shared-edge regression checks 256 pixels
for unwanted double alpha blending. Nineteen Python tests and four native
UI/controller configurations passed. A 1008-frame CPU fake-backend test covered
14 composite views, fog/shading variants, zoom extremes and huge off-map values:
64 slots maximum, four uploads/frame, 6432 indexed line candidates maximum.
This fake backend does not validate Vulkan texture identity or lifetime.

## Live result: visual acceptance FAILED

One copied-save pose in Area06 F021 was loaded, with XYZ equal to the previous
exact-stock audit point. Four final-swapchain V1/V2 pairs matched pose, view center,
floor, zoom, viewport and feature settings. The reference canvas again matched the
exact installed stock V1 capture at every sampled pixel (RGB MAE zero).

Actual image inspection found repeated raster content across tiles and missing
opaque active-floor fill. Vector wall positions still match. The new numerical
tile-to-swapchain check found only 46/2438 smooth opaque samples within 8 RGB levels
at default zoom, MAE 79.229 against the projected source tiles. This is a rendering
failure, not a passed material comparison. The expected source tile itself has
opaque floor pixels and passed file integrity validation.

A separate diagnostic build used already-uploaded direct texture IDs, with the
same failure and identical sampled pixel result. Its telemetry reports 26 resident
slots and 26 ready visible tiles but only 11 distinct backend texture IDs. This is
evidence to investigate texture identity/lifetime in the native backend; a root
cause has not been established. No fix is claimed. The fake-backend test cannot
detect this native aliasing behavior.

Private evidence roots, relative to `.local/atlas2/`:

- `audit-qa/runs/parity05/matching-view-comparisons.json` — four paired captures.
- `audit-qa/runs/parity05/private-pixel-comparison.json` — V1/V2 RGB differences.
- `audit-qa/runs/parity05/tile-projection-verification.json` — source/final check.
- `audit-qa/runs/parity05fix/matching-view-comparisons.json` — diagnostic retry.
- `audit-qa/runs/parity05fix/tile-projection-verification.json` — retry unchanged.
- `parity-content-validation.json`, `parity-cache-test.json`, `parity-cache-fix-test.json`.

The image files remain local and are not attached or uploaded. No Library IDs were
created: the original delegation prohibits uploading game-derived frames there.

## Diagnostic timing, not accepted quality-equivalent performance

Six alternating 20-second ETW/native phases completed at the fixed point, three
per renderer. Reference ETW medians: 668.584, 668.582, 669.161 ms. Static medians:
16.665, 16.671, 16.651 ms. Full-map Draw CPU elapsed medians: reference 666.598,
666.609, 667.437 ms; static 0.458, 0.435, 0.459 ms. ETW retained 77 reference and
3551 static presents. Raw evidence: `audit-qa/runs/parity05/independent-audit-summary.json`.

These timings describe the broken native raster output and MUST NOT be promoted
as performance after successful visual parity. The earlier prototype performance
audit remains a measurement of that prototype, not visual acceptance of this tier.

## Remaining scope

The existing finite teleport coverage stays eight destinations in four areas/eight
layers. Twelve areas are unavailable in the inspected owned QA copies; no flags
were unlocked. New parity restart/death acceptance is deferred because the visual
failure must be repaired first. Previous prototype graceful-restart checks passed;
no supported safe death trigger has been verified, and no raw health writes were
attempted. No additional game area or progression content is reported here.

The transient connection notification did not cause duplicate launches. Exactly
one native process was verified after reconnect; both batch05 processes were
closed normally in sequence. The GPU lease was released and the test install was
restored to the preserved prototype and baseline packs for handoff.
