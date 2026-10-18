# Independent performance audit — interim checkpoint

The extreme V1 timing is independently validated at one heavy copied-save point in Area06/F021. Do not extrapolate this result to all maps. The exact installed native V1 binary (SHA256 `887f5baf7e149ea7604e4e037fd5eef43a0ad483a8dcb649a6122636d906c557`) was copied into a separate guarded profile, with byte-identical asset bundle. The source installation was never modified. Its QA trace was fully omitted during the three accepted stock captures. All accepted ETW captures ran in the same host account as their private native process. A prior cross-account attempt produced no CSV and was rejected.

## Release and instrumentation audit

Both retained V1 map compilation and experimental map compilation use `-O2` and `NDEBUG`; `-g` retains symbols without disabling optimization. Eight relevant geometry/style/input headers are byte-identical after newline normalization. The remaining features header only adds a function declaration for static visibility. The existing V1 cache guards remain: area geometry loads once, interior/cut caches persist for stable area/layer/LOD, and no benchmark command forces invalidation. There is one elapsed timer around the whole map Draw call, one hook per native present, no timing calls inside triangle loops, and no per-triangle profiling or geometry serialization. Extra layer conformance scans and the legacy raw QA JSON are suppressed during the instrumented measurement. Native raw sample arrays are written only after recording stops.

The CPU timer uses `std::chrono::duration<double,std::milli>` and reports elapsed wall time of the CPU submission path, including any scheduling/waits within that scope; it is not exclusive thread CPU time. FPS is 1000 divided by mean present interval in ms. Independent [PresentMon console](https://github.com/GameTechDev/PresentMon/blob/v2.6.0/README-ConsoleApplication.md) ETW rows provide `MsBetweenPresents`; the official portable v2.6.0 executable was digest-verified (`b2a706bc6ad475749e3b7e3409263aa1e6906d45bdcf993f6dbc0f660188f1af`) and signature-valid. No service was installed and no input events were tracked.

## Independent stock V1 repeats

Same frozen copied save, 1920×1080, zoom 13.5, native pause menu, fog enabled, BB_PREP_WORKERS=0, 60 FPS limit. Two initial ETW rows per capture are excluded. Map-canvas comparison of the trace-enabled and trace-free stock runs matched all 252,904 sampled pixels exactly.

| Repeat | Retained frames | Median ms | p95 ms | FPS from mean |
| --- | ---: | ---: | ---: | ---: |
| 1 | 27 | 644.2540 | 648.4048 | 1.5511 |
| 2 | 27 | 646.2003 | 655.8665 | 1.5431 |
| 3 | 27 | 645.5460 | 657.8999 | 1.5457 |

## Prototype reference/static repeats against simultaneous ETW

The reference map canvas also matched the exact stock V1 at all 252,904 sampled pixels. Header labels are anonymized in the prototype. ETW and native capture windows overlap but have different startup/shutdown boundaries; these are distribution comparisons, not frame-by-frame pairs.

| Mode/repeat | ETW frames | ETW median / p95 ms | Native median ms | Map CPU median / p95 ms |
| --- | ---: | ---: | ---: | ---: |
| reference 1 | 27 | 642.4862 / 653.5006 | 642.5580 | 640.6386 / 651.4134 |
| static 1 | 1185 | 16.6749 / 18.1566 | 16.6659 | 0.3402 / 0.7597 |
| static 2 | 1181 | 16.6606 / 18.1383 | 16.6670 | 0.3648 / 0.7665 |
| reference 2 | 27 | 643.1447 / 657.2011 | 643.2014 | 641.1280 / 655.5897 |
| reference 3 | 27 | 641.9722 / 652.9324 | 642.1432 | 640.3865 / 653.0159 |
| static 3 | 1189 | 16.6674 / 18.2846 | 16.6664 | 0.3263 / 0.7621 |

V2 still has the documented visual simplifications; these data do not establish final visual-parity performance, moving-gameplay FPS, all-map speedup, or a closed-map lag fix. ETW GPU metrics are retained separately and describe whole-process per-present attribution, not map-only GPU cost.

## Flag diagnosis and ongoing copied-profile inspection

The current frozen profile exposes 45 authored targets: eight unlocked/eligible, 37 false unlock flags, zero unknown unlock or condition reads. Every absent area therefore has readably false unlocks in this profile; missing map data or a global unsupported adapter is not the cause. No flags or arbitrary coordinates were written. Five prior QA save sources passed read-only receipt, reparse-point, exact file-set and hash inspection before separate frozen copies were prepared. The native census loads these copies one at a time, requests no travel, reads flag values and closes each process normally.

Benchmark processes are closed. The separate census is still active at this interim checkpoint; consult `.local/atlas2/copied-save-census.json` for current profile counts. A bounded cleanup worker waits for census completion and no remaining game process, then restores the preserved prototype, verifies original-save isolation and releases reservation `atlas2-parent-window-20261018-batch04`. Its final status is `.local/atlas2/audit-cleanup.json`. No process is forcibly killed.

## Private evidence

`.local/atlas2/build-parity-audit.json`, `stock-audit-preparation.json`, `approved-copy-inspection.json`; `.local/atlas2/audit-qa/runs/stock-clean04/stock-open-summary.json`, `stock-closed-summary.json`, `stock-map-parity.json`; `.local/atlas2/audit-qa/runs/atlas2-audit04/independent-audit-summary.json`, `reference-stock-canvas-parity.json`, `flag-state-summary.json`, native sample JSON and ETW CSV files. Raw game logs and all images stay private.

## Completed copied-profile census and cleanup

All five receipt-verified QA copies completed guarded inspection. Each exposes the same eight eligible destination IDs in the same four areas; no additional area was found and no unlock/condition read was unknown. Every original QA source remained hash-identical. No census teleport was requested. All test games exited normally. The private test installation was restored to the preserved prototype, original-save isolation validation passed, and the GPU mutex was released at **2026-10-18 22:18:05.9865433 UTC**. Final machine-readable evidence: `.local/atlas2/independent-audit-final.json`, `copied-save-census.json` and `audit-cleanup.json`. There is no remaining launch/permission blocker. Broad visual parity, death regression and gameplay beyond the finite tested points remain unverified.
