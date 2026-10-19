# Full-pack native checkpoint — batch07

The complete 16-area, 602-view package has passed a bounded native checkpoint.
There are zero failed executed gates and four explicit coverage/acceptance gaps
below. This is a private experimental test package, not complete gameplay
acceptance or a release. No remote push, external distribution or image upload
was performed.

The tested native source is `064b13a74b25aec06a55a87acfb69757aa40d21e`.
The binary SHA256 is
`775c58a7183c23003e7e5698f21ae03049550d864d34817feffdd61d732551b5`;
the full pack index SHA256 is
`fcb871e80fd3f42857001a2d720f060e1ac945fdcab43e1cf4c39bd5f9b9ed7d`.
The normal private install still has fog enabled and `BB_PREP_WORKERS=0`.

## Executed checks

- Three real Vulkan synthetic phases pass: safe undersized-pool rejection,
  normal lifecycle, and injected allocation failure/recovery. Each positive
  phase checks six stages and 41,472 GPU pixel samples, including shared-content
  placement and return to a previously used floor. Images created/destroyed
  balance at 198/198 normally and 199/199 with injection.
- First full-pack map use begins with no loaded area and zero tile slots. The
  first map CPU scope is **198.7974 ms**; correlated complete-visible-tile readiness
  is **0.5 s**. Readiness includes control polling, not button-to-photon latency;
  this is a fresh process cache, not a promise of cold OS/shader caches.
- Eleven manual floor samples force **146 evictions and 146 new texture
  creations**. Maximum total slots is **64**, including up to 51 retiring slots;
  upload requests remain at most four/frame and prepared external views at most
  one. Backend ownership stays distinct and automatic floor selection restores.
- Sixteen native control checks pass: zoom, pan, recenter, manual/automatic floor,
  repeated close/reopen, disable/re-enable, input capture/release and fixed pose.
- Four default/maximum/minimum/Fit same-view V1/V2 pairs pass the operational
  raster regression limits. RGB MAE is 0.61748 / 0.68715 / 0.03194 / 1.44063.
  This rejects missing/repeated tiles at these sampled views; it is not pixel
  identity or human readability acceptance. All images remain private.
- All eight currently eligible discovered travel targets pass actual arrival,
  loaded-region, XYZ and V1/V2 automatic-floor checks. Pose delta is zero in every
  pair. Coverage is **4/16 areas and 8/602 layers**, as listed below.
- Normal close and same-private-save restart pass: PID 5344 to 16532, same loaded
  region, zero XYZ reload delta and F024 restored with matching V1/V2 selection.

| Area | Sampled live layer IDs | Destinations |
| --- | --- | --- |
| Area01 | F004 | 1 |
| Area04 | F009, F030 | 2 |
| Area05 | F015 | 1 |
| Area06 | F021, F024, F028, F029 | 4 |

Manual floor switching and offline coverage are not counted as loaded-player
pose coverage. Every other layer is explicitly unverified in the full live
coverage manifest. These finite samples do not establish every-coordinate,
boundary, staircase or overlap traversal correctness.

## Measured scope

At one fixed pose under the native pause menu, six independent 12-second ETW
phases alternate three V1 and three V2 samples. The V1 reference canvas first
matches the exact pinned stock reference at RGB MAE zero.

| Measurement | V1 medians across three phases | V2 medians across three phases |
| --- | --- | --- |
| Present interval | 716.76–720.46 ms | 16.657–16.662 ms |
| Complete map CPU scope | 714.87–718.16 ms | 0.392–0.467 ms |
| Retained ETW frames | 36 total | 2,122 total |

These are one paused point, not a general gameplay speedup factor. ETW GPU busy
medians vary 38.54–104.06 ms for V1 and 15.73–16.59 ms for V2, with whole-process
attribution. They do not isolate map-only GPU work, and the small V1 frame count
and pacing/queue behavior limit that comparison.

A separate continuously active-world series passes five six-second conditions:
disabled, enabled/closed, static/open, enabled/closed, disabled. Pose and unpaused
state remain fixed. Present medians are 16.665–16.667 ms in all five; open-map CPU
median is 0.414 ms. This uses native present/map CPU hooks, not independent GPU
timing. UI-disabled is a same-process command, not a startup-disabled baseline.
No general closed-map gameplay-lag fix is claimed.

The tile payload bound remains 17,305,600 bytes. This excludes driver allocation
overhead and is **not physical tile VRAM measurement**. A separate process-memory
sample is retained with its whole-game/shared-GPU scope clearly marked.

## Remaining gates

1. Twelve areas have no eligible discovered target in the inspected copied saves:
   Area02, Area03 and Area07–Area16. They need a suitable owned progressed copied
   save. No unlock-memory changes were made.
2. Death/respawn is unverified and was not forced. No verified ordinary-input death
   route exists from the available test points, and supported controls expose no
   death command. Unknown health-memory writes and unbounded blind movement were
   not used. Successful restart/load is not substituted for death/respawn.
3. Continuous natural staircase/overlap traversal remains unverified. Offline
   height/hysteresis tests, manual floor changes and travel/load changes pass,
   but do not replace that gameplay observation.
4. Human navigation readability remains unverified. Four numeric raster checks
   pass; no subjective local human review was performed. Documented antialiasing,
   hatch/stroke and non-default-zoom differences still apply.

## Isolation, evidence and launch

Fresh post-run verification confirms all 15 original save files, the pinned
original runtime and original game executable are hash-identical. The original
source remains at `4ee4a0e`, with its two prior line-ending changes and untracked
test file preserved. Private-save guards, geometry-free normal assets, fog and
zero preparation workers pass. Prototype rollback/checkpoints are retained.

Both native game processes closed normally. No synthetic/native test process
remained when the shared reservation was released at
**2026-10-19 03:46:02.7689214 UTC**. No forced termination was used.

The local test entry is `.local/atlas2/Atlas2-test/Start-Atlas2.cmd`; it opens the
private launcher, whose Play action uses private saves. Keep the adjacent
`.local/atlas2/parity-full16/` folder in place. Use an idle, coordinated GPU window
with no other game process. Do not start the binary directly. System
Install/Update/Uninstall actions are disabled in this experimental profile.

Anonymous technical evidence:

- `.local/atlas2/full-native-checkpoint.json`
- `.local/atlas2/full-live-coverage-manifest.json`
- `.local/atlas2/native-window-final-state.json`
- `.local/atlas2/original-post-full-native-facts.json`
- `.local/atlas2/isolation-tests.json`
- `.local/atlas2/synthetic-fullstyle-tests07/results.json`
- `.local/atlas2/audit-qa/runs/full07/` contains the individual cold, eviction,
  active-world, input, raster, independent ETW, travel and restart JSON reports.

Raw game logs and game-derived images in the private session must not be attached
to chat or Library. The technical reports above use anonymous area/layer IDs.
