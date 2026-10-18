# Local live checkpoint — batch02

Native binary: preserved prototype `d553827`, using the verified retained 1.9
runtime and public V1 source baseline `4ee4a0edf00ca87797e40f7ad73c27c9b2198625`.
One game process used a private copied save. Normal reveal rules remained enabled;
only discovered, currently eligible native destinations were requested.

## Confirmed coverage

| Area | Confirmed layer IDs | Destination samples | Matched pose/layer |
| --- | --- | --- | --- |
| Area01 | F004 | 1 | 1 |
| Area04 | F009, F030 | 2 | 2 |
| Area05 | F015 | 1 | 1 |
| Area06 | F021, F024, F028, F029 | 4 | 4 |

All eight arrivals reported native completion and matched the expected loaded block
and authored XYZ within 0.141 native units. V1/V2 pose deltas were zero in all eight
pairs. Strict V1, strict lookup and the rendered automatic layer agreed. There were
zero observed layer mismatches. These are eight sampled points in 4/16 areas and
8/602 layers. Twelve areas and 594 layers remain without a live destination sample;
the copied save exposes no eligible target in those twelve areas. It does not grant
coverage of all coordinates, stairs, overlap transitions or boundaries.

The initial one-point driver attempt timed out before comparison. A separate fresh
same-pose sample succeeded. The bounded eight-point retry then completed. The driver
now allows a short loading-fade settling interval and preserves confirmed arrival
evidence if a later comparison step times out. No uncertain accepted request is
automatically followed by another teleport.

## Live checks and bounded cache

- Four same-view pairs matched at default, maximum, minimum and Fit zoom; eight
  game-derived images remain private. Their visual acceptance is still unverified.
- Thirteen checks passed: input capture/release, pan/recenter, manual floor and
  automatic restoration, three close/reopen cycles, UI disable/re-enable.
- Passive samples observed at most 64 total slots including retiring textures,
  four uploads/frame, and 17,305,600 bytes of retained CPU RGBA and requested GPU
  pixel payload. No tile-integrity failure was observed. This excludes Vulkan
  driver allocation overhead and is not a physical VRAM measurement.

## Measurements and limits

At one stationary matched pose under the native pause menu, two eight-second static
samples observed UI frame cadence about 60 Hz and Atlas2 CPU submission medians
0.02845/0.0228 ms. Two reference samples observed about 1.53/1.52 Hz. This is
diagnostic UI cadence in this instrumented build: reference mode also runs extra
V1 layer checks, and no clean V1 executable timing baseline was collected. It is
not a measured gameplay speedup factor or CPU/GPU frame-time comparison.

The same-session UI-disabled and enabled-closed conditions were sampled. UI-disabled
uses a command in an Atlas2-enabled process; it is not a startup-disabled mod
baseline. Adapter-wide GPU utilization and aggregate process CPU usage are saved
with those limits. No closed-map lag fix is claimed. A 0.5 s reopen-to-ready sample
includes control polling and already-used assets; first-open hitch was not measured.

Known raster appearance deviations remain listed in VISUAL-PARITY.md, including
materials, fills/hatching, shading toggle, context composition, stroke widths and
maximum-zoom resolution. Pixel identity and navigation readability have not passed.
Death and restart remain untested; loading was observed during all eight teleports.

## Local evidence and shutdown

Evidence is under `.local/atlas2/qa/runs/batch02/`:
`comparison-summary.json`, `matching-view-comparisons.json`, `input-checks.json`,
`passive-cache-observation.json`, `performance-observations.json`. Raw logs and
images are private and must not be attached to chat or Library.
`.local/atlas2/live-coverage-manifest.json` records every unverified layer explicitly.

The private process received a normal window-close request and exited. The shared
GPU mutex was released at **2026-10-18 20:58:57.4265015 UTC**. No forced termination
was used in this batch. Post-run isolation validation passed; all 15 original save
files remained hash-identical. The original Atlas installation, game and settings
were not used as write targets. No remote push or release occurred.

## Follow-up measurement and capture correction

See PERFORMANCE-CHECKPOINT.md for the completed 36-series present-hook/CPU measurement and copied-save restart. The batch02 same-view telemetry remains valid, but its `output_*` images precede Atlas composition and are rejected for map visual review. Batch03 uses the supported final-swapchain `map-ui_*` hook; its four actual UI pairs remain private. No visual identity/readability pass is claimed. Raw flag 0 versus -1 was not separately retained, so absent discovered targets must not all be described as conclusively locked.
