# Atlas2 local experiment

This is an isolated static-map prototype based on public V1 commit
`4ee4a0edf00ca87797e40f7ad73c27c9b2198625`. It is local development work;
there is no remote push, release, public asset distribution, or AwakenChan integration.
The original source checkout, installed Atlas, game files, settings and saves are retained.

## Architecture

- `bake.cpp` is a CPU-only offline rasterizer for already validated local V1 packs.
  It preserves area identities, X/Z coordinates, Y heights and authored layer ordering.
  The first quality setting is 8 pixels per native world unit, 256-pixel tiles,
  2-pixel gutters, and a sparse LOD pyramid. No full-world bitmap is allocated.
- Each `AreaNN/manifest.json` records source/generator/feature identities, explicit
  world-to-image matrix, orientation, bounds, valid rectangular extent, units,
  floor metadata and every tile's coordinate and SHA-256. The area manifest and
  local spatial grid are hash-pinned by the parent index. Tile data is bounded
  zlib-compressed RGBA, checked before upload.
- `core.h` provides a deterministic 8-unit lookup grid. It tests only the triangles
  in the current cell with the same float interpolation and ordering as V1.
  It falls back to the closest authored anchor outside walkable geometry.
  Strict conformance tests use no history. Live mode retains the previous floor
  if its local height error is within 0.35 native units of the best surface;
  this explicit hysteresis can differ from V1 near ambiguous overlaps. Large
  movements, invalid positions and area changes reset continuity. Manual override
  remains available through the developer command interface.
- `bbport_map_static.cpp` keeps only the current area's grid and tile metadata.
  It submits visible context/current-floor imagery through the pinned ImGui texture
  protocol. The cache has **64 total slots including retiring textures**, a maximum
  of 4 uploads per frame, and at most 8 retirement requests per frame. LOD coarsens
  if more than 48 relevant visible tiles would be requested. Missing/corrupt data
  fails closed with a generic message and bounded negative caching.
- Geometry is stripped from normal runtime map assets. The original V1 geometry
  is loaded lazily for one reference area only when developer comparison is selected.
  The original V1 draw path and guarded game adapter are retained. Player/facing,
  lamps, pickups, NPCs, native travel, input capture and game menu hooks stay live.
- Static slices carry the authored reveal-rule indices required by V1's geometry
  probes. Runtime flag decisions occur before tile loops; unknown rules stay hidden.
  The private test profile defaults to fog enabled. No exploration flags are edited.
- `BB_PREP_WORKERS=0` remains in both private launch paths. This prototype isolates
  map drawing; it does not claim to fix gameplay stalls with the map closed.

## Explicit visual differences in this first baseline

Floor triangles, height layers, outlines and wall locations are retained. Decoration
is simplified: the parchment texture, enclosed-interior fill/hatching and cut hatching
are not baked yet. Context floors use alpha 27 instead of V1's near/far 38/27 split;
height shading uses each floor's local range; outlines/walls have fixed world widths.
The elevation-shading toggle currently affects the V1 reference only. These are
documented prototype deviations, not claims of pixel-identical visual conformance.
Navigation readability and native texture seams still require live visual review.
See [the source-only visual parity checklist](VISUAL-PARITY.md) for exact retained,
omitted and changed features, stroke/color formulas, zoom scaling and the prepared
matching-view comparison protocol. No gameplay speedup factor has been measured.

## Build and test

Use the owned private CPython and existing local CLANG64 toolchain. All output goes
under this worktree's ignored `.local/atlas2` directory. `build_local.py` validates
the retained native 1.9 executable's code section against the hash-verified pinned
reference, checks that the three replaced V1 source files match the selected commit,
compiles only changed map objects, and links them ahead of the unchanged retained
archives. Compilation is sequential; the linker uses one thread. It never mutates
the retained build. A fresh full native rebuild remains a future reproducibility check.

`bake_all.py` builds fresh private packs; `test_core.cpp` checks mathematical transforms,
negative Z orientation, bounds/invalid positions, strict V1 layer conformance at finite
deterministic probes, tile hashes and malformed/missing tile rejection. `test_cache.cpp`
stress-tests zoom/pan/area/layer changes with an explicitly fake CPU texture backend.
Its results do not measure Vulkan lifetime, VRAM overhead, GPU time or game frame time.
`run_regressions.py` runs retained V1 Python suites and headless native UI/controller tests.

`prepare_test.py` creates a fresh private installation, verifies the supported game
fingerprint, copies and hashes savedata, disables updates/online integration, and
rehashes the explicitly experimental local manifest. `finalize_test.py` refreshes
that private install after a rebuild. `verify_test.py` validates both launch paths,
geometry-free live assets, fog, workers and the copied-save path guard. The guard
rejects user/save paths outside the private experiment root.
The private installation/update/uninstallation scripts are inert; use its dedicated
`Start-Atlas2.cmd` entry point. It does not replace an existing Atlas installation.

## Developer comparison and live coverage

No native game is launched by generation, build or offline tests. Obtain a reserved
GPU window from the parent task before invoking `launch_session.py --reserved-window
<coordination-label> --label <generic-session-id>` with the test install's CPython.
`hold_native_lease.ps1` acquires `Local\Piranesi.Validation.SingleWorker` without
waiting, checks game/Blender processes and current GPU status, then maintains a
heartbeat. The launcher verifies both that heartbeat and the held OS mutex before
each child launch. Release using the per-reservation request path in the lease
record; the holder waits for game processes to exit before releasing. No process
is automatically terminated by this lease helper.
It reuses the existing local opt-in test driver without modifying that original file
and pins a local snapshot of it for both parent/child startup. It creates a fresh
copied-save session. Run only one game process at a time. `drive_game.py` sends one
named logical input or requests normal window closure for the verified private PID.

The private cross-volume preparation overlay explicitly uses the runtime's existing
`beside_game=False` implementation, keeping generated game views inside this
worktree. The default runner otherwise creates `mod-game-*` beside the game on D:;
that location is outside this task's write boundary. This one local script change
is rehashed in the private dependency/manifest closure. The original installed
runner and game remain untouched.

The command file accepts `atlas2-static`, `atlas2-reference`, `atlas2-overlay`,
`atlas2-floor N`, and `atlas2-floor-auto`. Both render paths share the same pose,
canvas, map transform and selected floor. The extra sanitized `.atlas2.json` trace
contains pose, floor comparison, transform roundtrip error, cache counts and submission
time. Numeric roundtrip error is not a measured visual-alignment error.
Schema-2 telemetry is atomically replaced and carries process ID, UTC time, sequence,
command acknowledgement, actual render-frame pose, backend-ready tile count and
native travel status. Correlated request IDs are executed once; stale traces and
unconfirmed commands cannot become successful samples.

`atlas2-travel N` is gated by experimental mode and `BB_ATLAS_QA=1`. It accepts only
currently available discovered destinations and calls the existing guarded native
travel adapter. `compare_session.py` attaches to an existing copied-save session,
requests only those destinations, checks region/XYZ after travel, then compares V1
and V2 at a stable matched pose. Failed/inconclusive arrivals remain explicit.
The default batch is two destinations and a bounded time budget. A known native
guard rejection is unavailable coverage; uncertain accepted requests stop the batch.
Floor differences at a matched pose are mismatches, including hysteresis differences.
Zero revealed tiles never count as visual acceptance. `coverage_manifest.py`
records all 602 planned layers with unverified live gaps until actual observations
exist; offline probes never become gameplay passes.
Offline geometry anchors are **not** native teleport targets.

Live testing remains pending until a reserved window is available: arrival/floor
confirmation, map-open/closed/disabled performance at matched positions, first-open
hitch, steady CPU/GPU frame times, actual texture allocation, death/load/restart and
visual readability. Record exact tested destinations and area/layer pairs, plus
unavailable areas. Finite samples never establish every-coordinate coverage.

All reports use Area01–Area16 or generic IDs. Private game-derived preview images,
raw native traces and assets stay local and must not be attached to chat or Library.
Rights review is required before any future public distribution of generated maps.
