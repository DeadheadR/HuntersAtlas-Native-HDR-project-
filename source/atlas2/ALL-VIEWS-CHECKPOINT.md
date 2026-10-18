# Full improved-style generation — in progress

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

Further required checks remain pending: full 602 validation, updated native cold
opening and cache eviction, local normal/max-zoom readability, live layer transitions,
and a bounded copied-save death/respawn/restart if feasible through ordinary input.
The pinned runtime's existing `BB_PAD_FILE` hook supports button names and four
0..255 stick axes. `supported_gameplay_pad.py` restricts gameplay probes to sticks
and circle, limits each hold to 1.5 seconds, validates the private PID/lease and
always releases input. No health or unlock-memory writes are added.

Twelve areas remain unavailable in the inspected progressed-save copies. Their
offline packs do not count as live coverage. No real gameplay/map image uploads,
public release, remote push or working-install replacement are authorized here.
