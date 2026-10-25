# Illustrated map source pipeline

This folder contains the offline illustration and passage-sheet bakers, the compiled-map payload compiler, and the reviewed source artwork. Generated work products are written under this folder's `work/` and `assets/<region>/` directories. Do not commit generated map data, game files, save data, raw extracts, captures, or review/private audit material.

## Inputs

Use Python 3.12 and install this folder's `requirements.txt` in an isolated environment: NumPy 2.5.4, SciPy 1.18.1, Pillow 12.3.0, Shapely 2.2.0 (with GEOS), and Soulstruct 2.3.2 for game extraction. Pip installs the extraction package's companion dependencies. Provide:

- `ATLAS_REFERENCE_DIR`: root of extracted reference data. Both supported layouts work: `features.json`, `atlas.json`, and `maps/<region>.json`; or `maps/features.json`, `maps/atlas.json`, and `maps/<region>.json` (the package-smoke materialized-assets layout).
- `ATLAS_GAME_DIR`: the user's own extracted game data directory, used only for the selected region's collision, navmesh, placement, and map-offset inputs.
- Optionally `ATLAS_GENERATOR_SOURCE`, `ATLAS_WORK_DIR`, `ATLAS_ASSET_DIR`, and `ATLAS_PYTHON_DEPS` to select those locations explicitly.

Reference inputs can be extracted from the supported Windows release ZIP; game data comes from the user's own extracted game copy. Neither is included here. `ATLAS_BASE_MAPS` points to the verified compiled-vector map package used as the compiler's base; pass `--base-maps` explicitly when it is outside this folder. The base must have the supported 16-region index. The compiler creates/updates a separate candidate directory and records a safety receipt; it refuses unsafe candidate replacement.

## Bake and compile

From the repository root in PowerShell, with the variables above set:

```powershell
$pipeline = (Resolve-Path source/illustrated).Path
python "$pipeline/bake_all.py"
```

`bake_all.py` performs collision extraction, navmesh extraction, physical support filtering, navigation geometry, overlap detection, passage-sheet generation, and illustration placement for all regions in the reference index. It uses the forest atlas for `m27_00_00_00` and the urban atlas for the other regions; each region receives actual baked placements rather than an empty illustration placeholder. Then compile the selected maps:

```powershell
python "$pipeline/compile_all.py" --base-maps <verified-maps-baked> `
  --candidate-maps <new-candidate-directory> `
  --work-root <work-root> --assets-root <asset-root> `
  --report-root <report-root> --map-id m27_00_00_00
```

Use repeated `--map-id` arguments for additional regions. `compile_navigation.py` is the one-region compiler and exposes the same `--base-maps`, `--candidate-maps`, `--work-root`, `--assets-root`, and `--report` options. Keep the candidate output separate from installed player files and review the emitted reports before packaging.

## Native integration build

The integration patch was compiled against the pinned Windows 1.9 native source baseline at upstream commit `652f9a494c47cc8c1ab16f28b456372eaa8103f8` (the retained release 1.2/v19 rebuild baseline). A repeatable integration build needs the corresponding Windows CLANG64 toolchain, build tree, baseline link-argument JSON, and baseline executable/object set. Those machine-specific build products are deliberately not included in source. Supply them explicitly:

```powershell
python source/illustrated/build_native.py `
  --source-dir source/compact `
  --base-source source `
  --base-build <matching-native-build-directory> `
  --link-arguments <maintainer-link-arguments.json> `
  --toolchain <pinned-clang64-bin> `
  --build-dir <new-output-directory>
```

The script replaces only the named renderer objects in the captured baseline link command and writes a receipt. This is a baseline integration build, not a clean full native rebuild. For a full rebuild, follow `SOURCE-BUILD.md` for the pinned upstream revision, vendor source, dependencies, and MSYS2 CLANG64 toolchain, then rebuild the baseline before applying this integration. Do not substitute a different baseline without validating its source revision and object compatibility.

The two PNG atlases and prompt text files in `assets/` are the original reviewed illustration inputs. Their prompts describe image generation only; the runtime consumes baked geometry and UVs. Before building/staging native runtime art, convert both RGBA PNGs into the native `BBRA` byte format (12-byte magic/width/height header followed by unmodified RGBA pixels):

```powershell
python "$pipeline/prepare_atlases.py" --output-dir <native-build-output>/art
```

This preserves each atlas's alpha channel and dimensions without resampling. The two resulting `.bbra` files must be placed in the runtime art directory consumed through `BB_MAP_ART_DIR`.
