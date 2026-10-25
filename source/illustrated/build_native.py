"""Build an Atlas renderer candidate by replacing exactly three native objects.

This script is deliberately isolated from the installed Atlas package. It uses
the existing maintainer link arguments and leaves all unrelated native objects
and libraries in place. Run only after source copies and build inputs are ready.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
DEFAULT_BASE_SOURCE = REPO / "source"

REPLACEMENTS = (
    ("map_vector.cpp", "bbport_map_static.cpp.obj", "-DATLAS_VECTOR_BUILD"),
    ("bbport_map.cpp", "bbport_map.cpp.obj", None),
    ("vector_backend.cpp", "imgui_impl_vulkan.cpp.obj", "-DIMGUI_IMPL_VULKAN_NO_PROTOTYPES"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def find_one_object(args: list[str], basename: str) -> int:
    hits = [i for i, value in enumerate(args)
            if Path(value.replace("\\", "/")).name.casefold() == basename.casefold()]
    if len(hits) != 1:
        raise RuntimeError(f"Expected exactly one link input named {basename}; found {len(hits)}")
    return hits[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--base-source", type=Path, default=DEFAULT_BASE_SOURCE)
    parser.add_argument("--base-build", type=Path, required=True,
                        help="build directory matching the pinned native baseline")
    parser.add_argument("--link-arguments", type=Path, required=True,
                        help="maintainer-captured baseline link argument JSON")
    parser.add_argument("--toolchain", type=Path, required=True,
                        help="pinned CLANG64 bin directory containing clang++.exe")
    parser.add_argument("--build-dir", type=Path, default=Path(__file__).resolve().parent.parent / "build")
    parser.add_argument("--baseline-exe", type=Path,
                        help="optional baseline executable for the build receipt")
    args = parser.parse_args()

    clang = args.toolchain / "clang++.exe"
    glslc = args.toolchain / "glslc.exe"
    source_dir = args.source_dir.resolve()
    base_source = args.base_source.resolve()
    build_dir = args.build_dir.resolve()
    if not clang.is_file():
        raise FileNotFoundError(f"Clang not found: {clang}")
    if not args.link_arguments.is_file():
        raise FileNotFoundError(f"Link argument file not found: {args.link_arguments}")
    for filename, _, _ in REPLACEMENTS:
        source = source_dir / filename
        if not source.is_file():
            raise FileNotFoundError(f"Renderer source not found: {source}")

    build_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(args.toolchain) + os.pathsep + env.get("PATH", "")
    shader = source_dir / "vector.vert"
    if not shader.is_file():
        raise FileNotFoundError(f"Vector shader source not found: {shader}")
    shader_binary = build_dir / "vector.spv"
    with (build_dir / "vector-shader.compile.log").open("wb") as log:
        subprocess.run([str(glslc), str(shader), "-o", str(shader_binary)],
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    raw_shader = shader_binary.read_bytes()
    if len(raw_shader) % 4:
        raise ValueError("Compiled vector shader size is not word aligned")
    words = struct.unpack(f"<{len(raw_shader) // 4}I", raw_shader)
    (build_dir / "vector_shader.h").write_text(
        "static const uint32_t atlas_vector_shader[] = {" + ",".join(map(str, words)) + "};\n",
        encoding="utf-8")
    include_dirs = (
        base_source / "atlas2",
        base_source / "native/gpu/third_party/imgui",
        base_source / "native/gpu/third_party/imgui/backends",
        base_source / "native/gpu/shim",
        source_dir,
        build_dir,
    )
    common = [str(clang), "-std=c++23", "-O2", "-DNDEBUG", "-DNOMINMAX", "-Wl,--threads=1"]
    common.extend("-I" + str(path) for path in include_dirs)

    built_objects: dict[str, Path] = {}
    for filename, object_name, define in REPLACEMENTS:
        output = build_dir / object_name
        command = common.copy()
        if define:
            command.append(define)
        command.extend(["-c", str(source_dir / filename), "-o", str(output)])
        with (build_dir / (filename + ".compile.log")).open("wb") as log:
            subprocess.run(command, cwd=args.base_build, env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        built_objects[object_name] = output

    original = json.loads(args.link_arguments.read_text(encoding="utf-8"))
    if not isinstance(original, list) or not original:
        raise ValueError("Link arguments must be a non-empty JSON array")
    link_args = [str(clang), *[str(value) for value in original[1:]]]
    replaced_inputs: list[dict[str, str]] = []
    for filename, object_name, _ in REPLACEMENTS:
        at = find_one_object(link_args, object_name)
        old = link_args[at]
        link_args[at] = str(built_objects[object_name]).replace("\\", "/")
        replaced_inputs.append({"source": filename, "replaced_object": old,
                                "new_object": link_args[at]})

    if "-o" not in link_args:
        raise ValueError("Baseline link arguments do not contain -o")
    out_at = link_args.index("-o") + 1
    candidate = build_dir / "bb-probe-illustrated.exe"
    link_args[out_at] = str(candidate).replace("\\", "/")
    if "-lvulkan-1" not in link_args:
        link_args.append("-lvulkan-1")
    response = build_dir / "illustrated-link.rsp"
    # Windows command-line quoting matches the existing maintainer recipe.
    import subprocess as _subprocess
    response.write_text(_subprocess.list2cmdline(link_args[1:]), encoding="utf-8")
    with (build_dir / "link.log").open("wb") as log:
        subprocess.run([str(clang), "@" + str(response)], cwd=args.base_build,
                       env=env, stdout=log, stderr=subprocess.STDOUT, check=True)

    receipt = {
        "candidate": str(candidate),
        "candidate_sha256": sha256(candidate),
        "baseline_executable": str(args.baseline_exe) if args.baseline_exe else None,
        "baseline_executable_sha256": sha256(args.baseline_exe) if args.baseline_exe and args.baseline_exe.is_file() else None,
        "link_arguments": str(args.link_arguments),
        "link_cwd": str(args.base_build),
        "replacements": replaced_inputs,
        "sources": {name: sha256(source_dir / name) for name in [*[n for n, _, _ in REPLACEMENTS], "illustrated_draw.h", "illustrated_legend.h", "vector.vert"]},
        "preservation_rule": "All original link arguments and inputs are preserved except the three named objects, output path, and Vulkan loader flag if absent.",
    }
    (build_dir / "build-native-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"build_native: {exc}", file=sys.stderr)
        raise SystemExit(1)
