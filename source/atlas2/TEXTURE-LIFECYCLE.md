# Texture ownership repair — batch06

The batch05 failure was a descriptor-capacity mismatch, followed by unsafe
allocation-failure handling. The retained overlay created 16 sampled-image
descriptors. One font and four art textures left eleven tile descriptors, matching
the eleven distinct IDs observed for 26 supposedly ready tiles. The tile cache
itself permits 64 slots, including textures waiting for retirement.

The experimental overlay now reserves `CacheSlots + 32 = 96` image descriptors.
The original installation is unchanged; an Atlas2-disabled source build retains
the previous pool size. Capacity is shared through `texture_budget.h`, so resident
and retiring tiles are covered together. Descriptor capacity does not preallocate
96 map images or change the 64-slot texture/pixel-payload limit.

The Vulkan backend now initializes the allocation output and returns on failure.
An unsuccessful texture creation releases its image/view/memory, leaves no TexID
or BackendUserData published and remains pending for retry. Pending retry requests
consume the next frame's four-tile upload budget. The build tool retains the pinned
overlay's existing input, QA and present hooks, patching its capacity line only;
the public source owner has the same capacity fix for normal source builds.

## Synthetic GPU regression

The fixture is generated solely from code: 128 uniquely colored, numbered images,
plus a view reusing one image in all cells. It contains no game-derived content.
`test_vulkan_tiles.cpp` runs the actual cache, ImGui and Vulkan backend into a
headless framebuffer and reads GPU pixels back. It does not start an emulator,
read saves or create a visible window.

The same fixture and harness are linked against the retained backend and the
patched backend. Results are in `.local/atlas2/synthetic-test06/results.json`:

| Phase | Result |
| --- | --- |
| Retained backend, pool 16 | Safely rejected the allocation failure at request 19, before submitting the affected frame |
| Patched backend, pool 96 | Five stages pass, 34,560 sampled GPU pixels correct |
| Patched backend, pool 96, one injected allocation failure | Same five stages and 34,560 pixels pass after retry |

The four unique-image stages alternate between disjoint sets of 48 visible tiles,
then return to evicted content. Distinct live texture objects must have distinct
backend IDs. The fifth stage legitimately shares one texture across 48 placements
and requires exactly one image ID in the draw commands. Both positive runs reached
64 resident/retiring slots. Instrumented actual tile copies to GPU stayed at four
per frame, including the injected-failure recovery. Backend image creation and
destruction balance was 198/198 normally and 199/199 with the injected failure.
The final rerun also includes queued-for-retirement textures that still have
Status OK in the ownership identity check; all three phases pass that stricter check.

The harness waits for its own queue before readback, so it is a conservative
ownership/identity regression, not an asynchronous fence stress or performance
test. Native pan/zoom testing remains necessary for the full game's frame lifetime.

Reproduction: generate a fresh fixture with `make_synthetic_tiles.py`, build the
isolated runtime with `build_local.py`, then run `run_synthetic_tests.py` with the
retained build/toolchain, new native object directory and a freshly held shared
GPU lease. The runner reports failure if a positive phase, pixel comparison,
ownership check, bounded warmup, cache limit or image balance check fails.

The batch05 captures and timing remain rejected for visual acceptance. Further
same-pose native evidence belongs to `audit-qa/runs/parity06`; it must be assessed
before accepting performance of the repaired quality tier.

## Native verification of the repair

Four final-swapchain pairs in Area06 F021 match pose, layer, center, zoom and
settings at 1920x1080. Normal fog/reveal remains enabled. At default zoom there
are now 26 ready slots and 26 distinct backend IDs; the other three snapshots also
have one distinct ID per resident slot (26, 42 and 40). Integrity failures are zero.

| View | Earlier broken RGB MAE | Repaired RGB MAE |
| --- | ---: | ---: |
| Default | 20.7262 | 0.6175 |
| Scaled maximum | 36.0302 | 0.6871 |
| Scaled minimum | 0.2292 | 0.0319 |
| Fit | 7.9028 | 1.4406 |

These are sampled RGB differences against the unchanged V1 reference on the
map canvas, not perceptual/semantic identity or navigation-readability scores.
The source-tile projection probe includes walls, icons and edge fades above the
tiles, so its unmasked opaque-pixel error is not a base-only equivalence test.
`accept_raster_checkpoint.py` rejects the old aliasing result and accepts the four
repaired views with explicit operational thresholds, capture hashes and identity
checks. It does not claim pixel identity. Full subjective navigation acceptance,
zoom-dependent decoration widths and native-equivalent antialiasing remain open.

Only after this check passed, six alternating 20-second ETW/native phases were
recorded. The V1 reference again matched the exact original stock canvas at every
sampled pixel (RGB MAE zero). Warm ETW frame-interval medians in milliseconds:

| Repeat | V1 | Atlas2 |
| --- | ---: | ---: |
| 1 | 646.0172 | 16.6631 |
| 2 | 649.1198 | 16.6525 |
| 3 | 646.5357 | 16.6723 |

V1 Draw CPU elapsed medians: 644.0229, 646.4208, 645.4234 ms. Atlas2: 0.47425,
0.39305, 0.43195 ms. ETW retained 79 V1 and 3556 Atlas2 presents. Atlas2 present
p95: 18.5468, 18.2276, 18.4024 ms; average cadence approximately 59.83–60.00 FPS.
V1 average cadence was 1.53–1.55 FPS. The third V1 run includes one 877 ms outlier;
its samples are retained. These are one fixed warm paused-menu point and three
windows per renderer, not all-area performance or post-repair cold-open results.
ETW GPU attribution remains whole-process, not map-only GPU time. No improvement
to closed-map gameplay lag is claimed.

Private evidence: `audit-qa/runs/parity06/raster-correctness-verification.json`,
`private-pixel-comparison.json`, `reference-stock-canvas-parity.json` and
`independent-audit-summary.json`. Images remain local; none were uploaded or
attached. Finite destination coverage is still the previous eight samples in four
areas; this repair adds four views at one existing point, not new area coverage.

The repaired build also passed a graceful close/restart using the same private
save directory: new process ID, same loaded block, XYZ delta zero, automatic floor
F021 again, and matching V1/V2 snapshots. No death trigger or raw health-memory
write was used. Death regression and twelve unavailable areas remain untested.

Native repair commit: `2b743f7`; binary SHA-256:
`4038dcddd5d5e7020a25c49bad2a8b596e941396a5a17e98dc6bac3023fb8f41`.
The repaired binary/config/build evidence is preserved separately in
`.local/atlas2/checkpoints/parity-fixed-2b743f7/`. The earlier prototype is preserved
independently; source work is local to `atlas2-static-maps`, with no remote push.

Handoff: both native sessions were closed normally, synthetic processes completed,
the shared lease was released, and the private install was restored to prototype
SHA-256 `ff79c34f11a738f1dd234b0427f6e731071360d23cbd03bce645b9720ee5e0ce`
and baseline packs. All 15 original save-file hashes and original installed native
binary hash are unchanged. `parity-repair-checkpoint.json` records the final checks.
