# Async loading checkpoint — batch08

The isolated full 16-area/602-view package now has optional asynchronous CPU
metadata preparation. The tested binary SHA256 is
`bcf512cf4749b63687bd2eb103a6dcae0e142225cfd79604227aba778b0d1132`.
Pack contents and index remain unchanged at
`fcb871e80fd3f42857001a2d720f060e1ac945fdcab43e1cf4c39bd5f9b9ed7d`.
This checkpoint supersedes the synchronous first-open result in
[FULL-NATIVE-CHECKPOINT.md](FULL-NATIVE-CHECKPOINT.md), not its historical evidence.

## First-open engineering work — completed

A CPU-only reproduction identified approximately 190.5 ms in Area06 area/grid
loading and another 21.3 ms in first-view preparation. These separate harness
timings identify the dominant work; they are not an exact decomposition of the
previous 198.7974 ms native first-map scope.

`BB_ATLAS2_ASYNC_LOAD=1` stages area/grid and selected-view/line metadata through
one CPU job slot. File hashes, schema/bounds checks and floor identities are
unchanged. The worker owns local data only: it does not call ImGui/Vulkan, query
game flags, mutate player state or render geometry. A completed result is adopted
on the caller thread. A changed area/floor discards stale results; a bad result
is rejected without rereading it every frame. Shutdown joins the one owned job.
The private launcher exports the opt-in flag; synchronous rollback remains usable.

No more than one job is owned at once. Area input retains the existing bounded
reads, view files are limited to 16 MiB and line files to 8 MiB. One selected
external view is prepared. The 64 texture slots, four uploads/frame, 96-image
descriptor pool, fog rules and pinned `BB_PREP_WORKERS=0` remain unchanged. The
new CPU file loader is separate from the pinned renderer preparation workers.

At the same fresh-process, empty-cache Area06 pose/menu state:

| Native measurement | Synchronous batch07 | Async batch08 |
| --- | --- | --- |
| First map CPU scope | 198.7974 ms | 2.0666 ms |
| Maximum map CPU scope in startup series | 198.7974 ms | 4.5695 ms |
| Maximum present interval in startup series | 206.2065 ms | 20.793 ms |
| Correlated full visible-tile readiness | 0.500 s | 0.515 s |

The async area and view worker timings were 211.125 and 18.236 ms. Work is moved
off the render thread, not eliminated. A loading placeholder is displayed until
validated metadata is ready, then bounded visible tiles become ready. The ready
time includes control polling; it is not button-to-photon latency. OS/shader
caches may be warm. This one case does not establish zero hitches everywhere;
four bounded tile reads/decodes still happen on the caller thread. The CPU-only
16-area stress test observed a maximum caller scope of 33.285 ms across its
sampled views, so there is no universal 16.7 ms frame guarantee.

Executed validation includes 31 Python tests, 72 retained V1 Python tests and
four native UI/controller suites; all pass. Six synchronous and six asynchronous
missing/corrupt/layer/transform metadata cases pass. CPU async tests cover all
16 area loads, stale area/view requests and shutdown with an in-flight job,
with at most one owned job. Real Vulkan lifecycle/failure tests pass six stages
per positive phase, each with 41,472 GPU pixel checks. Native full-pack cache
eviction, four same-view raster regressions and five active-world timing
conditions pass. All four raster RGB errors match the prior accepted samples.

## Natural height/layer traversal — completed finite sample

A connected route was derived from existing Area01 geometry near an already
eligible discovered target. Ordinary stick input, with no teleport between
walking samples, produced 65 pose samples and 15 paused V1/V2 checkpoints.
Observed height span was 1.14746 world units and layers changed F004 to F005;
every checkpoint matched V1. This demonstrates an ordinary height/layer
transition. It does not establish all staircases/overlaps or subjective visual
identification of the route as a particular staircase.

An earlier attempt stopped on an unconfirmed menu-button input and is retained.
The test driver now has bounded menu confirmation/retry. The successful height
run needed no retry. The selected input thresholds and short impulses are test
automation details, not changes to normal game controls.

## Death/respawn — actionable route dependency

Death/respawn was not forced and no pass is invented. Two geometry-derived
approaches from the same eligible Area01 target were attempted using ordinary
walking. The first stopped after four no-progress attempts. The alternate also
stopped at a local no-progress condition after a paused continuation.

Intermediate attempts exposed test-controller precision/menu interruptions;
their receipts are preserved separately. Smaller adaptive impulses and a
practical intermediate waypoint tolerance were implemented before the final
continuation. No health writes, unlock writes, collision bypass or unknown raw
addresses were used. No death screen or respawn cycle was observed.

The remaining blocker is a **verified reachable ordinary death route**. Rendered
floor triangles are not a complete collision/navigation model, so their void
edges cannot certify a reachable fall. Needed owner input is either directions
from an already eligible copied-save point to a known ordinary death, or manual
execution of that death on the isolated developer copy during a reserved window.
`observe_respawn.py` is prepared to require generic death text, an invalid-pose
load cycle and a freshly matched V1/V2 respawn; its actual death path remains
unverified until that dependency is supplied. All captures stay local.

## Remaining acceptance and evidence

- Owner dependency: 12 areas still have no eligible target in the inspected
  copied saves; a suitable owned progressed copy is needed. No new areas were
  unlocked. Previous eight-destination/four-area coverage belongs to batch07;
  current-build ordinary traversal and first-use tests must not be silently
  presented as new live coverage of all those places.
- Owner dependency: human navigation readability/local image review remains
  outstanding. No gameplay/map image uploads or alternate upload routes are used.
- Engineering fix completed: the reproduced 199 ms first-open CPU stall. Remaining
  bounded tile I/O and driver allocation overhead are explicit performance limits,
  not an unmeasured claim of zero frame hitches or tile-only physical VRAM.
- Additional engineering regression: the existing eight-target loop was not
  repeated on this async binary before returning this scoped checkpoint. Current
  native cases cover Area01 and Area06; the earlier synchronous binary covers
  eight targets in four areas. Repeating the already eligible loop needs no new
  save or unlock and remains a clearly separate next test.

The updated binary also passed same-copy restart from PID 10076 to 2280. The loaded
region and F004 agree; reload XYZ differs by **2.92398 world units**, within the
existing three-unit test tolerance. Exact saved-pose identity is not claimed;
V1/V2 agree at the new loaded pose. Both processes closed normally. Zero native
and synthetic processes remained when the reservation was released at
**2026-10-19 04:27:09.8058761 UTC**. All 15 original save files, original executable
identities and preexisting source work passed fresh post-run checks.

Primary reports are `.local/atlas2/async-native-checkpoint.json` and the individual
JSON files under `.local/atlas2/audit-qa/runs/async08/`. CPU and negative evidence is
in `async-loading-tests.json`, `async-negative-tests.json` and
`async-regression-tests.json`; Vulkan evidence is in `synthetic-async-tests08/`.
Final process/lease, restart and protected-state results are pinned by the JSON
checkpoint. Raw logs, OCR text and game-derived images must stay private.

The private entry remains `.local/atlas2/Atlas2-test/Start-Atlas2.cmd` followed by
its Play action, in an idle coordinated GPU window with no other game process.
Keep the adjacent `parity-full16` folder in place. Do not run the binary directly.
System install/update/uninstall actions remain disabled. Both the original
prototype and synchronous full-package rollback `checkpoints/full-345936c/` are
retained. No remote push or distribution is performed.
