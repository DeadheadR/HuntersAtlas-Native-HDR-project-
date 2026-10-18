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
