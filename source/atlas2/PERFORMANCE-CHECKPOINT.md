# Controlled local performance checkpoint — batch03

Four fixed copied-save poses, one native process at a time, 1920×1080, zoom 13.5, 60 FPS limit, fog enabled, BB_PREP_WORKERS=0. No raster generation, compilation or other reserved native job ran during measurement. V1 means the retained reference draw path inside the instrumented prototype; the original installed executable was not modified or timed as a separate process.

Each warm mode has two roughly 12-second repetitions; first two samples per interval are excluded. CPU values below are mean ± sample SD of complete map Draw elapsed wall time. Present intervals come directly from the once-per-present hook, include frame pacing and are separate from map CPU time.

| Area | Mode | Samples | Map CPU ms, mean ± SD | Present ms, mean ± SD | Present p95 ms | FPS |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Area01 | V1 reference | 1458 | 7.486 ± 0.199 | 16.670 ± 0.304 | 17.156 | 59.987 |
| Area01 | V2 static | 1464 | 0.203 ± 0.080 | 16.670 ± 0.303 | 17.131 | 59.987 |
| Area04 | V1 reference | 23 | 933.801 ± 12.567 | 935.746 ± 12.652 | 956.497 | 1.069 |
| Area04 | V2 static | 1464 | 0.326 ± 0.113 | 16.668 ± 0.388 | 17.149 | 59.996 |
| Area05 | V1 reference | 39 | 573.360 ± 30.873 | 575.255 ± 30.817 | 603.856 | 1.738 |
| Area05 | V2 static | 1466 | 0.467 ± 0.090 | 16.669 ± 0.284 | 17.140 | 59.993 |
| Area06 | V1 reference | 34 | 653.465 ± 8.248 | 655.702 ± 8.242 | 667.733 | 1.525 |
| Area06 | V2 static | 1465 | 0.371 ± 0.130 | 16.668 ± 0.272 | 17.124 | 59.995 |

## Cold and closed states

| Area | V1 first-use window max present ms | V2 first-use window max present ms | V1 closed FPS | V2 closed FPS | UI-disabled FPS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Area01 | 85.989 | 101.737 | 59.489 | 59.973 | 59.995 |
| Area04 | 1375.739 | 337.867 | 59.996 | 59.511 | 59.802 |
| Area05 | 968.043 | 288.491 | 59.997 | 59.981 | 59.996 |
| Area06 | 960.902 | 190.695 | 59.888 | 59.705 | 59.993 |

Cold means the first use of that area/render path in this process, with all samples retained. OS, shader and shared UI caches may already be warm. Cold order was static then reference. These are observed maximum intervals in the first-use window, not full cold-start or click-to-ready latency. Full distributions, first CPU draw, setup CPU time and immutable raw samples are in the private JSON evidence.

UI-disabled uses a command in the same Atlas2-enabled process; it is not a startup-disabled executable baseline. Closed samples did not call map Draw, and no closed-gameplay lag fix is established. The map-open raster prototype omits documented material/hatching details and changes stroke widths; it is a lighter visual workload. Do not extrapolate a global speedup factor, final visual-parity performance or all-map performance. GPU timestamps and GPU frame time were not obtained. Frame counts are not independent statistical trials; the slow V1 cases have small samples. One driver interruption on a transient telemetry read preserved all native samples and resumed at the same PID/pose without relabeling warmed phases as cold.

## Coverage, restart and visual evidence

All four benchmark points retained matching V1/V2 pose and layer confirmation. Previously completed destination coverage remains eight destinations across four areas and eight layers; the benchmark does not establish all-coordinate coverage. The guarded adapter supports all 16 authored area inventories (45 targets). The current copied save exposes eight discovered/eligible targets in four areas; all 12 absent areas report zero discovered targets. Authored targets exist and the global guarded adapter reports support, so no per-area build rejection was observed. Raw flag results (0 versus unknown/read failure -1) were not retained separately. Consequently this proves no currently eligible warp, but does not fully distinguish a locked target from an unread flag group; a read-only per-flag health audit remains necessary before attributing every gap solely to character unlocks.

A normal close and relaunch of the same copied save passed: a different private native PID loaded the same block/layer with XYZ delta 0, followed by a successful same-pose V1/V2 comparison. Death was not attempted: no verified death trigger or verified normal-gameplay death route is available in the existing guarded test interface. No health, event flag, save or arbitrary-coordinate patches were used.

The original game-frame dump is before Atlas composition and was rejected for map visual review. The supported final-swapchain UI hook then captured four actual same-view pairs privately. Header controls matched exactly; sampled map RGB MAE was 16.364 at default, 31.296 at maximum zoom, 0.069 at minimum zoom, and 25.739 at Fit. This confirms appearance differences; it does not approve navigation readability or pixel equivalence. Images stay private and are never attached or uploaded.

A bounded read-only inventory found 17 save roots (including the original), 11 content identities and five existing QA copies with source receipts. Forty-one prior live QA JSON files expose only two distinct recorded poses in Area01/Area05, with at most eight eligible targets. Those records provide no evidence of broader unlocked coverage. Hash differences can reflect position or other saved state; alternate-profile flag coverage remains unverified. Recorded XYZ can extend offline projection tests but cannot bypass guarded native destinations. A future isolated copy of a receipt-verified alternate profile can be loaded to inventory flags; a profile with more discovered native destinations is needed to extend missing areas safely. No user decision is needed for this completed measurement batch.

## Evidence and shutdown

Private evidence: `.local/atlas2/qa/runs/batch03/performance-summary.json`, `measurements/`, `controlled-measurements.json`, `destination-inventory.json`, `restart-verification.json`, `private-pixel-comparison.json`, and `matching-view-comparisons.json`. Save/record inventories live at `.local/atlas2/copied-save-inventory.json` and `recorded-position-inventory.json`. No raw logs or images should be shared.

Both native processes exited after normal window-close requests. The shared native mutex was released at **2026-10-18 21:35:55.4743732 UTC**. Post-run copied-save isolation validation passed. The measurement binary remains archived separately, and the private test installation was restored to the preserved prototype. Original installation, game and save files were not write targets; no remote push or release occurred.
