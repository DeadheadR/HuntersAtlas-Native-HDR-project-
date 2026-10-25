# Atlas 3.1 compiled renderer

The current illustrated payload compiler and original art are in
`source/illustrated/`. Use its README and explicit-input `build_native.py` for
the current integration. This folder retains the legacy base/grid/hatch compiler
alongside the tested illustrated renderer and matching shader.

The shipped native executable links the pinned Windows 1.9 baseline with the
following replacements: bbport_map.cpp, map_vector.cpp, vector_backend.cpp and
the existing Atlas map art/features/overlay objects. Other baseline runtime and
GPU objects are unchanged. See native-build.json in the player package.

The offline compiler bake_vectors.cpp includes ../atlas2/parity_style.h and
requires C++23, zlib and OpenSSL. Build with include directories source/atlas2,
source/native/gpu/shim and source/native/gpu/third_party/imgui. Run it with
input reference-map JSON, output area directory and region ID (see main).
It emits losslessly compressed geometry and precompiled hatch levels, not images.

Native renderer: compile map_vector.cpp and bbport_map.cpp with the same include
paths and SDL3/Vulkan development headers. Compile vector_backend.cpp with
IMGUI_IMPL_VULKAN_NO_PROTOTYPES and this directory on the include path. The
included vector_shader.h is generated from vector.vert with glslc; rebuild it
after shader changes. Compile the current source/native map art and features,
and use the pinned overlay's descriptor capacity adjustment from
source/atlas2/build_local.py. Link these override objects BEFORE the pinned
libbbgpu.a, then use its ordinary bb-probe link inputs plus zlib, OpenSSL and
Vulkan. This avoids rebuilding unrelated native GPU/runtime objects.

The older scripts in this directory record historical compact build context.
Their workstation defaults are not the current public packaging command;
use the explicit inputs documented in `source/illustrated/README.md`.
All relevant source additions and generated shader source are supplied here.
The player runtime performs no build step and depends only on its ZIP contents.

The accompanying corresponding/ directory retains the full native baseline,
upstream Windows 1.9 source, dependency sources and their existing licenses.
The complete Atlas source tree is supplied alongside these compact additions.
# Compact compiled map renderer

This folder contains the runtime renderer and its shader. The illustrated
runtime is compiled from `map_vector.cpp`, `bbport_map.cpp`,
`vector_backend.cpp`, `vector.vert`, `illustrated_draw.h`, and
`illustrated_legend.h`. Maintain the matching offline generation sources in
`source/illustrated/`; see that folder's README for inputs, bake commands, and
the limitations of the pinned-baseline integration build.
