# Full improved-style pack — offline checks complete

All 602 views across 16 anonymous areas are generated and strictly verified.
The final catalog is approximately 9.66 GiB, within the unchanged 16 GiB output
cap and 16 GiB free-space reserve. The base generation completed in 11,127 seconds
from its preserved original start window. No native game was launched in this run.

Final validation checks 154,726 declared physical tile files, 742,247 nondegenerate
source-triangle centroids and 7,128 anchor roundtrips with zero raster gaps. The
runtime CPU cache harness passes 43,344 frames across all 602 views, with at most
64 slots including retiring textures and four upload requests/frame. Exactly one
external view remains prepared. This is not a physical VRAM measurement or a new
native performance result.

The inherited V1 interior topology helper reports one fill-budget skip. This
preexisting limit is recorded in the final report; all tested walkable triangle
centroids still have raster coverage. It is not a claim of semantic readability
or exhaustive world-coordinate coverage.

Two center-sampling gaps in Area11 were corrected through an isolated analytic
coverage stage, then its validated files were promoted with exact metadata backups.
The other 15 area manifests were retained, and all 14 previously accepted control
views have identical encoded pixels. See [SUBPIXEL-COVERAGE.md](SUBPIXEL-COVERAGE.md).
The complete full-pack profile is installed only in `.local/atlas2/Atlas2-test`,
with measurement/comparison enabled, fog enabled and `BB_PREP_WORKERS=0`.
The prototype binary/checkpoints and original working V1 remain available.

The remaining native stage requires a newly reserved GPU window from the parent.
It includes cold opening, real cache eviction, matched active/paused conditions,
supported copied-save travel, layer transitions and a bounded ordinary-input
death/respawn attempt if feasible, followed by restart. Twelve areas remain live
coverage gaps in the inspected copied saves. Offline checks are finite samples,
not every-coordinate or every-location gameplay coverage.

The new output is `.local/atlas2/parity-full16/`; original verified packs,
the 14-view parity set, prototype and repaired runtime rollback remain unchanged.
The target is exactly 602 authored views across 16 anonymous areas, all at 16
texels/native world unit. This is offline generation, not new live coverage.

## Resumable generation and limits

`bake_all_views.py` runs one CPU baker at a time. Each completed view writes its
external metadata and area checkpoint atomically; content-addressed tile writes
are atomic too. The controller refreshes the root index and records progress in
`generation-state.json`. Interrupted work can resume without replacing original
packs or discarding verified completed views. A process identity receipt and a
single-writer lock prevent duplicate controllers. Do not start a second run while
the recorded controller or worker is alive.

The output budget is 16 GiB, including retained baseline files, with a 16 GiB free
space reserve and a 4 GiB object budget per area. The controller also has a six-hour
wall-time limit. Reaching a bound stops owned CPU work and preserves atomic view
checkpoints. The job writes private anonymous logs; it never launches a game or
uses a GPU. The current controller was already running when the identity guard
was added, so its live PID/creation/image receipt was recorded and duplicate
resume rejection was explicitly verified.

Initial checkpoint: Area01's 13 and Area02's 12 views generated in approximately
44 seconds, total staged directory size 359,257,323 bytes including the copied
baseline. The next representative area takes about 18 seconds/view. Full output
therefore has a meaningful time/storage cost; live counts and final size must be
read from the state file, not inferred from the small-area rate.

## Compact lazy runtime format

Schema 3 keeps area identity, original lookup grid, layer order and common
coordinate conventions. Each floor has a separately hashed metadata file with
an explicit world-to-image matrix, bounds, active walkable extent, Y-height
extent, anchor/span, orientation and native-unit declaration. Fog/shading groups
refer to compact deduplicated tile sets. The runtime parses details for one active
external view and releases the previous view's metadata on a floor switch.
Schema 1/2 packs remain readable. No full floor triangle drawing is reintroduced.

The preflight found at most 12,218 active line segments, so the indexed line limit
is now 16,384. Tile cache remains 64 slots including retiring textures, four upload
requests/frame, with the repaired 96-image-descriptor pool. The raster still has
the previously documented non-default-zoom hatch-width and antialiasing differences.

## Checkpoint validation

- Initial 25 views: all declared tile files hashed/decoded and 17,613 nondegenerate
  source-triangle centroids covered; all-area anchor transform roundtrips checked.
- CPU cache: 1800 frames across those 25 views, maximum 64 slots and four requests
  per frame, no integrity failures.
- Five synthetic metadata cases pass: valid repeated floor reload, missing external
  file, corrupt content, wrong layer identity and header/body transform mismatch.
  Another floor remains usable when an unrelated file is absent; a bad active view
  is rejected once and cached as rejected rather than repeatedly read each frame.
- Existing 19 Python tests pass. `verify_full_pack.py` is prepared to validate all
  602 external files, line geometry/index completeness, source identities, explicit
  transforms and source-triangle centroid coverage after generation completes.

Further required native checks remain pending: updated native cold
opening and cache eviction, local normal/max-zoom readability, live layer transitions,
and a bounded copied-save death/respawn/restart if feasible through ordinary input.
The pinned runtime's existing `BB_PAD_FILE` hook supports button names and four
0..255 stick axes. `supported_gameplay_pad.py` restricts gameplay probes to sticks
and circle, limits each hold to 1.5 seconds, validates the private PID/lease and
always releases input. No health or unlock-memory writes are added.

Twelve areas remain unavailable in the inspected progressed-save copies. Their
offline packs do not count as live coverage. No real gameplay/map image uploads,
public release, remote push or working-install replacement are authorized here.

Prepared native QA instrumentation now counts all owned backend textures, including
retiring ones, separately from pending requests; cumulative creation/eviction/
collection counters prove that a cache test actually reloads content. Full-pack
cold tests require the completed 602-view validation hash and a genuinely empty
first-use cache. Manual reference rendering honors the explicit comparison floor;
automatic measurement mode still uses V1's own floor selection. Returning from a
forced manual floor clears that forced history before applying normal hysteresis.
A sixth synthetic overlap test covers this reset. V1 Python/native regressions
pass on the updated build. Full-pack native validation awaits its reserved GPU window.

The full-pack driver also has a separate `gameplay` stage. It resumes the copied
save through the existing ordinary options-button input hook, then samples five
six-second conditions: disabled, enabled/closed, static/open, enabled/closed,
disabled. Each sample requires the same valid pose and a continuously unpaused
native world. It restores the paused closed-map state afterward. These are native
present-hook/map-CPU samples at one stationary location, not independent GPU
timings or evidence that general closed-map gameplay lag is fixed. Three new
tests reject pause/gameplay misclassification; all 22 Atlas2 Python tests pass.

At 303 completed views the first controller exited after Windows denied an atomic
state-file replacement. Its existing Area09 baker remained alive; it was inspected
and supervised without launching another generator. The Windows reader/writer
contention was reproduced locally. Controller metadata now uses `ReplaceFileW`,
shared-delete readers, coherent single-read hashes and a five-second bounded retry.
Persistent controller errors stop only their own CPU child and retain completed
checkpoints. Four new IO tests pass, including replacement while an old reader
remains open; all 26 Atlas2 Python tests pass. The four frozen raster-generator
sources and their content identity are unchanged. Recovery must wait until that
existing baker exits and retain the original six-hour deadline and storage limits.

The original controller's verified creation time is preserved in
`generation-window.json`. Resume uses that same absolute deadline and the same
16 GiB output/reserve limits; it cannot silently reset the time window or raise
the storage cap. Three additional tests cover those bounds; all 29 Python tests
pass. This changes orchestration only, not raster output or generator identity.

Additional deterministic grid tests cover 12,309 strict V1-rule comparisons,
walkable triangle-edge boundaries in all 602 layers, height-varying triangles in
575 layers, distinct-height overlaps in 592 layers, and 207 two-layer overlap
jitter/transition cases with the normal hysteresis margin. The report pins the
baseline index and every grid hash. Overlap search uses at most 16 centroids per
layer: ten layers had no overlap found in that sample, which does not establish
absence. Height variation is a geometric category, not a semantic staircase label.
These remain offline checks and do not increase live teleport coverage.
