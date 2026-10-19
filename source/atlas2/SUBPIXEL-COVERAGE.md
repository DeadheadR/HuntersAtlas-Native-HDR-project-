# Subpixel coverage checkpoint

The strict centroid check found two uncovered samples in Area11 F012. Their
minimum projected triangle altitudes are approximately 0.565 and 0.800 pixels at
16 texels/world unit. Both are inside the image bounds. Center-only triangle
sampling leaves separated pixels along those thin shapes; the first sample's
nearest stored alpha pixel center is about 3.36 pixels away. This is a recorded
raster coverage failure, not a passed area or a reason to loosen the threshold.

The original generator's four frozen sources and content identity remain intact.
`coverage_raster.h` implements a separate offline analytic triangle/pixel area
intersection. `repair_coverage.cpp` rerenders only tiles touched by inventoried
thin geometry. It reuses the base generator's complete primitive order, materials,
height tint, mip conventions and fog-mask decisions. Only the identified textured
floor triangles receive analytic coverage; source geometry, transforms, layer
selection and runtime rendering code are unchanged.

The real-pack stage refuses incomplete generation or a scoped structural receipt.
A marked isolated trial permits the Area11 checkpoint without changing the main
catalog. New content-addressed objects and new view metadata are appended, old
objects/views remain intact, and prior area/root manifests are backed up. Stage
identity must include the compiled tool, its source/dependencies and the input
inventory. The same completed stage is idempotent. Output stays within 16 GiB,
with a 16 GiB free-space reserve, the original per-area object bound, and runtime
metadata-size bounds. The runtime still uses the existing 64-slot tiled cache.

Synthetic checks pass: 64 translated thin-triangle cases, 36 recovered center
sample gaps, area conservation and zero gutter-channel seam difference. An
end-to-end synthetic fixture recovers a missing centroid to alpha 93, keeps the
unrevealed fog variant empty, preserves original objects/views and exact rollback
metadata, and passes an idempotent rerun. The current runtime's CPU cache harness
accepts that repaired fixture for 72 frames with no integrity failures.

Game-derived trial repair and the final strict full-pack verification remain
pending. No native gameplay or new live area coverage is implied by these tests.
