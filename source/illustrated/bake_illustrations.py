#!/usr/bin/env python3
"""Bake deterministic, atlas-mapped decoration outside the Forbidden Woods paths.

This reads work/navigation.json and writes an independent illustration mesh.
It never changes the navigation surface or any game/release files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT = Path(__file__).resolve().parent
import shapely as sh
from shapely.geometry import LineString, Point, Polygon


DEFAULT_NAVIGATION = PROJECT / "work" / "navigation.json"
DEFAULT_OUTPUT = PROJECT / "work" / "illustrations.json"
SEED_DEFAULT = 20261025
ART_BAND_OUTER_M = 16.0
PATH_CLEARANCE_M = 0.35
SPACING_MIN_M = 10.0
SPACING_MAX_M = 14.0
PLACEMENT_LIMIT = 900
CELL_PADDING = 0.03  # fraction of each sprite cell, on every side

FOREST_ASSETS = (
    {"index": 0, "name": "tree", "size_range_m": [10.0, 16.0], "weight": 24},
    {"index": 1, "name": "dead_tree", "size_range_m": [10.0, 16.0], "weight": 10},
    {"index": 2, "name": "shrub", "size_range_m": [5.0, 10.0], "weight": 12},
    {"index": 3, "name": "tree", "size_range_m": [10.0, 16.0], "weight": 22},
    {"index": 4, "name": "boulder", "size_range_m": [5.0, 10.0], "weight": 12},
    {"index": 5, "name": "cliff", "size_range_m": [5.0, 10.0], "weight": 6},
    {"index": 6, "name": "roots", "size_range_m": [5.0, 10.0], "weight": 7},
    {"index": 7, "name": "outcrop", "size_range_m": [5.0, 10.0], "weight": 7},
)


URBAN_ASSETS = (
    {"index": 0, "name": "roof", "size_range_m": [5.0, 10.0], "weight": 2},
    {"index": 1, "name": "buttress", "size_range_m": [5.0, 10.0], "weight": 2},
    {"index": 2, "name": "tombstones", "size_range_m": [5.0, 10.0], "weight": 1},
    {"index": 3, "name": "masonry_rubble", "size_range_m": [5.0, 10.0], "weight": 2},
    {"index": 4, "name": "boulders", "size_range_m": [5.0, 10.0], "weight": 1},
    {"index": 5, "name": "cliff_rock", "size_range_m": [5.0, 10.0], "weight": 1},
    {"index": 6, "name": "roots", "size_range_m": [5.0, 10.0], "weight": 1},
    {"index": 7, "name": "dead_shrub_rubble", "size_range_m": [5.0, 10.0], "weight": 1},
)
ASSETS = FOREST_ASSETS


def polygon_parts(geometry: Any) -> Iterable[Polygon]:
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for child in geometry.geoms:
            yield from polygon_parts(child)


def build_surface(navigation: dict[str, Any]) -> Any:
    packed = navigation.get("surface", {}).get("triangles")
    if not isinstance(packed, list) or not packed:
        raise ValueError("navigation surface has no packed triangles")
    chunks = []
    for offset in range(0, len(packed), 4000):
        chunk = packed[offset : offset + 4000]
        triangles = []
        for i, t in enumerate(chunk, start=offset):
            if len(t) != 6:
                raise ValueError(f"surface triangle {i} is not three XZ pairs")
            triangles.append([(t[0], t[1]), (t[2], t[3]), (t[4], t[5])])
        chunks.append(sh.union_all(sh.polygons(triangles), grid_size=0.015))
    surface = sh.make_valid(sh.union_all(chunks, grid_size=0.015))
    if surface.is_empty or surface.area <= 0:
        raise ValueError("navigation surface union is empty")
    return surface


def canonical_exterior(poly: Polygon) -> list[tuple[float, float]]:
    """Return a stable CCW ring, rotated to its lexicographically least vertex."""
    coords = [(float(x), float(z)) for x, z in list(poly.exterior.coords)[:-1]]
    signed = sum(
        coords[i][0] * coords[(i + 1) % len(coords)][1]
        - coords[(i + 1) % len(coords)][0] * coords[i][1]
        for i in range(len(coords))
    )
    if signed < 0:
        coords.reverse()
    start = min(range(len(coords)), key=lambda i: (round(coords[i][0], 6), round(coords[i][1], 6)))
    return coords[start:] + coords[:start]


def stable_rng(seed: int, values: Iterable[float]) -> random.Random:
    payload = f"{seed}|" + "|".join(f"{v:.4f}" for v in values)
    digest = hashlib.sha256(payload.encode("ascii")).digest()
    return random.Random(int.from_bytes(digest[:8], "little"))


def ring_id(coords: list[tuple[float, float]]) -> str:
    payload = ";".join(f"{x:.4f},{z:.4f}" for x, z in coords)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()[:12]


def outward_normal(surface: Any, boundary: Point, tangent: tuple[float, float]) -> tuple[float, float]:
    # Canonical exterior rings are CCW, making the right-hand normal outward.
    nx, nz = tangent[1], -tangent[0]
    # Verify orientation against the complete union, including nearby components.
    probe = Point(boundary.x + nx * 0.2, boundary.y + nz * 0.2)
    if surface.contains(probe):
        nx, nz = -nx, -nz
    return nx, nz


def trace_tangent(line: LineString, distance: float) -> tuple[float, float] | None:
    length = line.length
    step = min(1.0, max(0.2, length / 20.0))
    before = line.interpolate((distance - step) % length)
    after = line.interpolate((distance + step) % length)
    tx, tz = after.x - before.x, after.y - before.y
    size = math.hypot(tx, tz)
    if size < 1e-8:
        return None
    return tx / size, tz / size


def atlas_info(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        raise FileNotFoundError(f"atlas image not found: {path}")
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is needed only to validate the optional atlas image") from exc
    with Image.open(path) as image:
        width, height = image.size
    # GPU UVs have fractional pixel boundaries; integer-sized cells are not
    # required. Preserve the generated image and its alpha without resampling.
    if width < 8 or height < 4 or abs(width / height - 2.0) > 0.02:
        raise ValueError(f"atlas dimensions {width}x{height} do not match the expected 4x2 layout")
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return {"path": str(path.resolve()), "width": width, "height": height, "sha256": h.hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navigation", type=Path, default=DEFAULT_NAVIGATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--atlas", type=Path, help="optional original 4x2 sprite atlas for metadata validation")
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    parser.add_argument("--max-placements", type=int, default=PLACEMENT_LIMIT)
    parser.add_argument("--style", choices=("forest", "urban"), default="forest")
    args = parser.parse_args()
    global ASSETS
    ASSETS = FOREST_ASSETS if args.style == "forest" else URBAN_ASSETS
    if not 2 <= args.max_placements <= PLACEMENT_LIMIT:
        raise ValueError(f"--max-placements must be within 2..{PLACEMENT_LIMIT}")

    navigation_path = args.navigation.resolve()
    navigation = json.loads(navigation_path.read_text(encoding="utf-8"))
    surface = build_surface(navigation)
    path_buffer = surface.buffer(PATH_CLEARANCE_M)
    allowed_fringe = sh.difference(surface.buffer(ART_BAND_OUTER_M), path_buffer)
    if allowed_fringe.is_empty:
        raise ValueError("decorative fringe is empty")

    polygons = sorted(
        polygon_parts(surface),
        key=lambda p: (
            round(p.bounds[0], 4), round(p.bounds[1], 4),
            round(p.bounds[2], 4), round(p.bounds[3], 4), round(p.area, 4),
        ),
    )
    rings: list[tuple[str, LineString]] = []
    for poly in polygons:
        if poly.area < 15.0 or poly.exterior.length < 24.0:
            continue
        coords = canonical_exterior(poly)
        closed = coords + [coords[0]]
        rings.append((ring_id(coords), LineString(closed)))
    rings.sort(key=lambda item: item[0])

    asset_weights = [a["weight"] for a in ASSETS]
    placements: list[dict[str, Any]] = []
    candidates_seen = 0
    for rid, line in rings:
        length = line.length
        spacing_rng = stable_rng(args.seed, (float(int(rid[:8], 16)), length))
        spacing = spacing_rng.uniform(SPACING_MIN_M, SPACING_MAX_M)
        phase = spacing_rng.uniform(0.0, spacing)
        sample_distance = phase
        sample_index = 0
        while sample_distance < length:
            tangent = trace_tangent(line, sample_distance)
            boundary = line.interpolate(sample_distance)
            if tangent is not None:
                normal = outward_normal(surface, boundary, tangent)
                rng = stable_rng(args.seed, (boundary.x, boundary.y, sample_index))
                asset = rng.choices(ASSETS, weights=asset_weights, k=1)[0]
                preferred_offset = rng.uniform(3.0, 7.0)
                # Nearby disconnected path islands can block the preferred point.
                # Search only along this boundary's outward normal and keep the
                # final center 3-7m from the complete path union.
                valid_offsets = []
                for candidate_offset in sorted(
                    {preferred_offset, *(3.0 + i * 0.25 for i in range(17))},
                    key=lambda value: (abs(value - preferred_offset), value),
                ):
                    candidate_center = Point(
                        boundary.x + normal[0] * candidate_offset,
                        boundary.y + normal[1] * candidate_offset,
                    )
                    candidate_distance = surface.distance(candidate_center)
                    if 3.0 - 1e-6 <= candidate_distance <= 7.0 + 1e-6:
                        valid_offsets.append(candidate_offset)
                if not valid_offsets:
                    sample_index += 1
                    sample_distance += spacing
                    continue
                offset = valid_offsets[0]
                size_min, size_max = asset["size_range_m"]
                width = rng.uniform(size_min, size_max)
                depth = rng.uniform(size_min, size_max)
                cx = boundary.x + normal[0] * offset
                cz = boundary.y + normal[1] * offset
                tx, tz = tangent
                corners = [
                    (cx - tx * width / 2 - normal[0] * depth / 2, cz - tz * width / 2 - normal[1] * depth / 2),
                    (cx + tx * width / 2 - normal[0] * depth / 2, cz + tz * width / 2 - normal[1] * depth / 2),
                    (cx + tx * width / 2 + normal[0] * depth / 2, cz + tz * width / 2 + normal[1] * depth / 2),
                    (cx - tx * width / 2 + normal[0] * depth / 2, cz - tz * width / 2 + normal[1] * depth / 2),
                ]
                full_quad = Polygon(corners)
                clipped = sh.intersection(full_quad, allowed_fringe)
                candidates_seen += 1
                if not clipped.is_empty and clipped.area >= 1.25:
                    placements.append(
                        {
                            "id": f"deco-{len(placements):04d}",
                            "asset_index": asset["index"],
                            "asset": asset["name"],
                            "ring_id": rid,
                            "boundary_anchor_xz": [round(boundary.x, 4), round(boundary.y, 4)],
                            "center_xz": [round(cx, 4), round(cz, 4)],
                            "offset_m": round(offset, 4),
                            "tangent_xz": [round(tx, 6), round(tz, 6)],
                            "outward_normal_xz": [round(normal[0], 6), round(normal[1], 6)],
                            "full_size_m": [round(width, 4), round(depth, 4)],
                            "source_quad_xz": [[round(x, 5), round(z, 5)] for x, z in corners],
                            "clipped_area_m2": round(float(clipped.area), 6),
                            "uv_cell": {"column": asset["index"] % 4, "row": asset["index"] // 4},
                            "geometry": clipped,
                            "quad_center": (cx, cz),
                            "quad_tangent": tangent,
                            "quad_normal": normal,
                            "quad_size": (width, depth),
                        }
                    )
            sample_index += 1
            sample_distance += spacing

    if len(placements) > args.max_placements:
        # Stable, evenly distributed cap; candidate spacing otherwise remains 10-14m.
        indices = [round(i * (len(placements) - 1) / (args.max_placements - 1)) for i in range(args.max_placements)]
        placements = [placements[i] for i in indices]
    if not 1 <= len(placements) <= args.max_placements:
        raise ValueError(f"decorative placement count {len(placements)} is outside 1..{args.max_placements}")

    vertices: list[list[float]] = []
    indices: list[int] = []
    vertex_lookup: dict[tuple[float, float, float, float], int] = {}
    art_triangles: list[Polygon] = []
    placed_asset_counts = {str(a["index"]): 0 for a in ASSETS}
    placed_area = 0.0
    expected_clipped_area = sum(float(p["clipped_area_m2"]) for p in placements)
    meshed_placements: list[dict[str, Any]] = []

    def intern_vertex(x: float, z: float, placement: dict[str, Any]) -> int:
        cx, cz = placement["quad_center"]
        tx, tz = placement["quad_tangent"]
        nx, nz = placement["quad_normal"]
        width, depth = placement["quad_size"]
        asset_index = placement["asset_index"]
        local_u = 0.5 + ((x - cx) * tx + (z - cz) * tz) / width
        # Atlas source rows read top to bottom; the outward side maps to the cell top.
        local_v = 0.5 - ((x - cx) * nx + (z - cz) * nz) / depth
        pad = CELL_PADDING / 4.0
        cell_w, cell_h = 0.25, 0.5
        col, row = asset_index % 4, asset_index // 4
        u = col * cell_w + pad + max(0.0, min(1.0, local_u)) * (cell_w - 2 * pad)
        v = row * cell_h + pad + max(0.0, min(1.0, local_v)) * (cell_h - 2 * pad)
        key = (round(x, 5), round(z, 5), round(u, 7), round(v, 7))
        found = vertex_lookup.get(key)
        if found is not None:
            return found
        found = len(vertices)
        vertex_lookup[key] = found
        vertices.append(list(key))
        return found

    for placement in placements:
        clipped = placement.pop("geometry")
        art_triangles_for_placement: list[Polygon] = []
        for poly in polygon_parts(clipped):
            mesh = sh.constrained_delaunay_triangles(poly)
            for triangle in polygon_parts(mesh):
                if triangle.area <= 1e-9:
                    continue
                if not poly.covers(triangle):
                    # Keep only fully contained constrained faces to avoid bridge artifacts.
                    continue
                coords = list(triangle.exterior.coords)[:3]
                tri_idx = [intern_vertex(float(x), float(z), placement) for x, z in coords]
                indices.extend(tri_idx)
                art_triangles_for_placement.append(triangle)
                art_triangles.append(triangle)
        art_area = sum(t.area for t in art_triangles_for_placement)
        if not art_triangles_for_placement:
            continue
        placement["mesh_area_m2"] = round(float(art_area), 6)
        placement["first_index"] = len(indices) - sum(3 for _ in art_triangles_for_placement)
        placement["index_count"] = len(art_triangles_for_placement) * 3
        placed_area += art_area
        placed_asset_counts[str(placement["asset_index"])] += 1
        for internal in ("quad_center", "quad_tangent", "quad_normal", "quad_size"):
            placement.pop(internal, None)
        meshed_placements.append(placement)

    placements = meshed_placements
    if not 1 <= len(placements) <= args.max_placements:
        raise ValueError(f"meshed placement count {len(placements)} is outside 1..{args.max_placements}")
    for index, placement in enumerate(placements):
        placement["id"] = f"deco-{index:04d}"

    if len(indices) % 3:
        raise AssertionError("illustration index buffer is not triangle aligned")
    art_mesh = sh.union_all(art_triangles) if art_triangles else Polygon()
    intersection_area = float(sh.intersection(art_mesh, surface).area)
    if intersection_area >= 1e-5:
        raise ValueError(f"illustration mesh intersects the original surface by {intersection_area} m2")
    if abs(placed_area - expected_clipped_area) >= 1e-3:
        raise ValueError(
            "constrained triangulation did not preserve clipped artwork area: "
            f"{placed_area} vs {expected_clipped_area} m2"
        )
    min_clearance = float(sh.distance(art_mesh, surface)) if not art_mesh.is_empty else None

    atlas = atlas_info(args.atlas.resolve() if args.atlas else None)
    output = {
        "schema": 1,
        "source": str(navigation_path),
        "atlas": atlas,
        "atlas_grid": {"columns": 4, "rows": 2, "cell_padding_fraction": CELL_PADDING},
        "world_coordinates": "XZ; UV coordinates use top-to-bottom atlas rows",
        "seed": args.seed,
        "label": "Artistic decorative placements; not surveyed tree or rock locations.",
        "constraints": {
            "sample_spacing_m": [SPACING_MIN_M, SPACING_MAX_M],
            "boundary_offset_m": [3.0, 7.0],
            "path_clearance_m": PATH_CLEARANCE_M,
            "outer_fringe_limit_m": ART_BAND_OUTER_M,
            "clip_against": "navigation surface.buffer(0.35m); sprites additionally limited to surface.buffer(16m)",
            "original_navigation_surface_edited": False,
        },
        "vertices": vertices,
        "indices": indices,
        "decorative_placements": placements,
        "qa": {
            "source_surface_area_m2": round(float(surface.area), 6),
            "source_surface_polygons": len(list(polygon_parts(surface))),
            "sampled_exterior_rings": len(rings),
            "candidate_samples": candidates_seen,
            "placement_count": len(placements),
            "placements_by_asset_index": placed_asset_counts,
            "artwork_triangle_count": len(indices) // 3,
            "artwork_mesh_area_m2": round(float(placed_area), 6),
            "mesh_surface_intersection_area_m2": round(intersection_area, 10),
            "minimum_mesh_to_surface_clearance_m": round(min_clearance, 6) if min_clearance is not None else None,
            "intersection_tolerance_m2": 1e-5,
            "all_vertices_have_uv": all(len(v) == 4 for v in vertices),
            "all_indices_in_range": all(0 <= i < len(vertices) for i in indices),
            "mesh_topology": "Constrained-Delaunay triangles clipped to the exterior decoration fringe; UVs remain affine projections of each full source quad.",
        },
    }
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "placements": len(placements),
                "vertices": len(vertices),
                "triangles": len(indices) // 3,
                "intersection_area_m2": intersection_area,
                "minimum_clearance_m": min_clearance,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
