"""Split overlap windows into true 3D-connected navmesh sheets.

The overlap IDs in navigation.json index the supported-triangle arrays. This
module keeps that provenance and writes a sidecar consumed optionally by
compile_navigation.py. Projected overlap is used only to build the clipped
render geometry; connectivity is determined in XYZ through shared full edges.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import shapely as sh
from shapely.geometry import Polygon
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parent


def _components(geometry: Any):
    if geometry is None or geometry.is_empty:
        return
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from _components(part)


def _packed(geometry: Any) -> dict[str, list[Any]]:
    geometry = sh.make_valid(sh.simplify(geometry, 0.035, preserve_topology=True))
    try:
        triangles = sh.constrained_delaunay_triangles(geometry)
    except Exception:
        candidate = sh.delaunay_triangles(geometry)
        triangles = sh.GeometryCollection(
            [part for part in _components(candidate) if geometry.covers(part)]
        )
    packed_triangles = []
    for polygon in _components(triangles):
        coords = list(polygon.exterior.coords)[:3]
        if len(coords) == 3:
            packed_triangles.append([round(float(v), 3) for point in coords for v in point[:2]])
    outlines = [
        [[round(float(x), 3), round(float(z), 3)] for x, z in ring.coords]
        for polygon in _components(geometry)
        for ring in (polygon.exterior, *polygon.interiors)
    ]
    return {"triangles": packed_triangles, "outlines": outlines}


class _UnionFind:
    def __init__(self, count: int) -> None:
        self.parent = list(range(count))
        self.rank = [0] * count

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        a, b = self.find(left), self.find(right)
        if a == b:
            return
        if self.rank[a] < self.rank[b]:
            a, b = b, a
        self.parent[b] = a
        if self.rank[a] == self.rank[b]:
            self.rank[a] += 1


def _weld_vertex_ids(triangles: np.ndarray, tolerance: float) -> np.ndarray:
    """Cluster XYZ endpoints within tolerance using neighboring hash cells."""
    points = np.asarray(triangles, dtype=np.float64).reshape((-1, 3))
    uf = _UnionFind(len(points))
    buckets: dict[tuple[int, int, int], list[int]] = {}
    inv = 1.0 / tolerance
    limit2 = tolerance * tolerance
    for index, point in enumerate(points):
        cell = tuple(math.floor(float(value) * inv) for value in point)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for other in buckets.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()):
                        delta = point - points[other]
                        if float(np.dot(delta, delta)) <= limit2:
                            uf.union(index, other)
        buckets.setdefault(cell, []).append(index)
    return np.fromiter((uf.find(i) for i in range(len(points))), dtype=np.int64, count=len(points))


def _core_sheet_components(triangles: np.ndarray, polygons: Any, region: Any,
                           tolerance: float) -> tuple[list[tuple[list[int], list[int]]], np.ndarray]:
    """Find core-connected sheets, then add casing context without merging them."""
    count = len(triangles)
    if not count:
        return [], np.zeros(0, dtype=bool)
    vertex_roots = _weld_vertex_ids(triangles, tolerance).reshape((-1, 3))
    core_areas = np.asarray(sh.area(sh.intersection(polygons, region)), dtype=np.float64)
    core_flags = core_areas > 1e-8
    core_uf = _UnionFind(count)
    adjacency = [set() for _ in range(count)]
    edge_owners: dict[tuple[int, int], list[tuple[int, tuple[float, float], tuple[float, float]]]] = {}
    for tri_id, roots in enumerate(vertex_roots):
        for corner_a, corner_b in ((0, 1), (1, 2), (2, 0)):
            a, b = roots[corner_a], roots[corner_b]
            if a == b:
                continue
            edge = (int(min(a, b)), int(max(a, b)))
            pa = tuple(float(v) for v in triangles[tri_id, corner_a, [0, 2]])
            pb = tuple(float(v) for v in triangles[tri_id, corner_b, [0, 2]])
            edge_owners.setdefault(edge, []).append((tri_id, pa, pb))

    for owners in edge_owners.values():
        if len(owners) < 2:
            continue
        for left_index in range(len(owners)):
            left, pa, pb = owners[left_index]
            for right_index in range(left_index + 1, len(owners)):
                right, _, _ = owners[right_index]
                adjacency[left].add(right)
                adjacency[right].add(left)
                if not core_flags[left] or not core_flags[right]:
                    continue
                # The shared edge must run through a meaningful portion of the
                # true overlap core; a casing-only ramp edge cannot merge floors.
                if sh.intersection(sh.LineString((pa, pb)), region).length > 0.02:
                    core_uf.union(left, right)

    groups: dict[int, list[int]] = {}
    for tri_id in np.flatnonzero(core_flags):
        groups.setdefault(core_uf.find(int(tri_id)), []).append(int(tri_id))
    core_groups = sorted(groups.values(), key=lambda group: min(group))
    owner_group = {tri_id: group_id for group_id, group in enumerate(core_groups) for tri_id in group}
    results = []
    for group_id, core_group in enumerate(core_groups):
        render_positions = set(core_group)
        queue = list(core_group)
        cursor = 0
        while cursor < len(queue):
            current = queue[cursor]
            cursor += 1
            for neighbor in adjacency[current]:
                # A context triangle can be used as casing by two sheets, but
                # traversal never enters another core sheet and joins them.
                if core_flags[neighbor] and owner_group.get(neighbor) != group_id:
                    continue
                if neighbor not in render_positions:
                    render_positions.add(neighbor)
                    queue.append(neighbor)
        results.append((core_group, sorted(render_positions)))
    return results, core_flags


def _record_window(overlap: dict[str, Any], window_buffer_m: float) -> Any:
    packed = overlap.get("overlap_geometry", {})
    polygons = []
    for raw in packed.get("triangles", []):
        values = np.asarray(raw, dtype=np.float64)
        if values.size == 6 and np.isfinite(values).all():
            polygon = Polygon(values.reshape((3, 2)))
            if polygon.is_valid and polygon.area > 1e-9:
                polygons.append(polygon)
    if not polygons:
        raise ValueError(f"overlap {overlap.get('id')} has no usable overlap geometry")
    region = sh.union_all(polygons, grid_size=0.015)
    return region, region.buffer(window_buffer_m)


def _height_on_triangle(triangle: np.ndarray, x: float, z: float) -> float | None:
    a, b, c = triangle
    den = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
    if abs(float(den)) < 1e-10:
        return None
    u = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / den
    v = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / den
    if min(u, v, 1.0 - u - v) < -1e-6:
        return None
    return float(u * a[1] + v * b[1] + (1.0 - u - v) * c[1])


def _sheet_self_overlap_pairs(surfaces: np.ndarray, core: Any, *, min_area: float = 0.12,
                              min_vertical_gap: float = 2.4) -> int:
    """Count projected source-face overlaps that remain vertically distinct."""
    if len(surfaces) < 2:
        return 0
    projected = sh.polygons(surfaces[:, :, [0, 2]])
    tree = STRtree(projected)
    pairs = tree.query(projected, predicate="intersects")
    if pairs.shape[1] == 0:
        return 0
    a, b = pairs
    keep = a < b
    a, b = a[keep], b[keep]
    if len(a) == 0:
        return 0
    intersections = sh.intersection(projected[a], projected[b])
    counts = 0
    for left, right, region in zip(a, b, intersections):
        if region.is_empty:
            continue
        region = sh.intersection(region, core)
        if region.is_empty or float(region.area) <= min_area:
            continue
        point = region.representative_point()
        ya = _height_on_triangle(surfaces[int(left)], point.x, point.y)
        yb = _height_on_triangle(surfaces[int(right)], point.x, point.y)
        if ya is not None and yb is not None and abs(ya - yb) > min_vertical_gap:
            counts += 1
    return counts


def _clip_y(points: list[np.ndarray], plane: float, keep_above: bool) -> list[np.ndarray]:
    """Sutherland-Hodgman clip of an XYZ polygon against one horizontal plane."""
    if not points:
        return []
    result: list[np.ndarray] = []
    previous = points[-1]
    prev_inside = previous[1] >= plane - 1e-9 if keep_above else previous[1] <= plane + 1e-9
    for current in points:
        curr_inside = current[1] >= plane - 1e-9 if keep_above else current[1] <= plane + 1e-9
        if curr_inside != prev_inside:
            dy = float(current[1] - previous[1])
            if abs(dy) > 1e-12:
                t = (plane - float(previous[1])) / dy
                result.append(previous + (current - previous) * t)
        if curr_inside:
            result.append(current)
        previous, prev_inside = current, curr_inside
    return result


def _fallback_bands(sheet: dict[str, Any], core: Any) -> list[dict[str, Any]]:
    """Split an internally ambiguous sheet into exact <=2 m bands in the core."""
    surfaces = np.asarray(sheet["surfaces_xyz"], dtype=np.float64).reshape((-1, 3, 3))
    source_ids = [int(v) for v in sheet["source_triangle_indices"]]
    if not len(surfaces):
        return []
    min_y, max_y = float(surfaces[:, :, 1].min()), float(surfaces[:, :, 1].max())
    first = math.floor(min_y / 2.0) * 2.0
    band_count = max(1, int(math.ceil((max_y - first) / 2.0)))
    physical_union = sh.union_all(sh.polygons(surfaces[:, :, [0, 2]]))
    physical_lines = sh.intersection(physical_union.boundary, core)
    physical_outlines = [
        [[round(float(x), 3), round(float(z), 3)] for x, z in line.coords]
        for line in _line_parts(physical_lines)
    ]
    output = []
    for band_index in range(band_count):
        low = first + band_index * 2.0
        high = low + 2.0
        clipped_triangles: list[list[list[float]]] = []
        surface_sources: list[int] = []
        band_polygons = []
        for src_index, original in zip(source_ids, surfaces):
            polygon = [np.asarray(point, dtype=np.float64) for point in original]
            polygon = _clip_y(polygon, low, True)
            # Half-open upper bounds avoid duplicating horizontal faces lying
            # exactly on a band seam; the final interval includes its ceiling.
            if band_index < band_count - 1:
                polygon = _clip_y(polygon, high - 1e-9, False)
            else:
                polygon = _clip_y(polygon, high, False)
            if len(polygon) < 3:
                continue
            projected = Polygon([(float(p[0]), float(p[2])) for p in polygon])
            if not projected.is_valid or projected.area <= 1e-9:
                continue
            clipped = sh.intersection(projected, core)
            if clipped.is_empty:
                continue
            for part in _components(clipped):
                try:
                    tessellation = sh.constrained_delaunay_triangles(part)
                except Exception:
                    tessellation = sh.GeometryCollection(
                        [candidate for candidate in _components(sh.delaunay_triangles(part))
                         if part.covers(candidate)]
                    )
                for tri_poly in _components(tessellation):
                    coords = list(tri_poly.exterior.coords)[:3]
                    if len(coords) != 3:
                        continue
                    xyz = []
                    for x, z in coords:
                        y = _height_on_triangle(original, float(x), float(z))
                        if y is None:
                            xyz = []
                            break
                        xyz.append([float(x), float(y), float(z)])
                    if len(xyz) != 3:
                        continue
                    face = np.asarray(xyz, dtype=np.float64)
                    if float(np.linalg.norm(np.cross(face[1] - face[0], face[2] - face[0]))) <= 1e-9:
                        continue
                    clipped_triangles.append(xyz)
                    surface_sources.append(src_index)
                    band_polygons.append(Polygon([(p[0], p[2]) for p in xyz]))
        if not band_polygons:
            continue
        geometry2d = sh.intersection(sh.union_all(band_polygons), core)
        if geometry2d.is_empty or geometry2d.area <= 1e-8:
            continue
        geometry = _packed(geometry2d)
        # Only the physical original component boundary is outlined. Band
        # caps and the overlap-window clip boundary never become walls.
        geometry["outlines"] = physical_outlines
        band_surfaces = np.asarray(clipped_triangles, dtype=np.float64)
        used_source_ids = sorted(set(surface_sources))
        included = set(used_source_ids)
        band = {
            "id": -1,
            "source_triangle_indices": used_source_ids,
            "surface_source_indices": surface_sources,
            "source_side_ids": {
                "upper": sorted(included & set(sheet["source_side_ids"].get("upper", []))),
                "lower": sorted(included & set(sheet["source_side_ids"].get("lower", []))),
            },
            "source_model_ids": list(sheet.get("source_model_ids", [])),
            "geometry": geometry,
            "surfaces_xyz": band_surfaces.tolist(),
            "min_y": float(band_surfaces[:, :, 1].min()),
            "max_y": float(band_surfaces[:, :, 1].max()),
            "mean_y": float(band_surfaces[:, :, 1].mean()),
            "bounds": [float(v) for v in geometry2d.bounds],
            "overlap_coverage_area": float(geometry2d.area),
            "core_triangle_count": len(used_source_ids),
            "context_triangle_count": 0,
            "self_overlap_ambiguous": False,
            "self_overlap_pair_count": 0,
            "triangle_count": len(clipped_triangles),
            "fallback": {
                "source_sheet_id": int(sheet["id"]),
                "band_index": band_index,
                "y_bounds": [low, high],
                "band_height_m": 2.0,
                "source_proof": "Original XYZ source triangles clipped by horizontal planes with linear edge interpolation, then clipped to overlap core; barycentric Y reconstructed on each original source plane.",
                "outlines_from_original_component_boundary": True,
                "no_band_cut_walls": True,
                "core_only_geometry": True,
            },
        }
        output.append(band)
    return output


def _line_parts(geometry: Any):
    if geometry is None or geometry.is_empty:
        return
    if geometry.geom_type in ("LineString", "LinearRing"):
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from _line_parts(part)


def _model_ids_by_supported_index(work_dir: Path, keep: np.ndarray) -> list[int | None]:
    inventory_path = work_dir / "navmesh-inventory.json"
    if not inventory_path.is_file():
        return [None] * int(np.count_nonzero(keep))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    by_original = np.full(len(keep), -1, dtype=np.int64)
    cursor = 0
    for row in inventory:
        size = int(row.get("triangles", 0))
        end = min(len(keep), cursor + max(size, 0))
        by_original[cursor:end] = int(row.get("model", -1))
        cursor += size
    return [int(v) if v >= 0 else None for v in by_original[np.flatnonzero(keep)]]


def _load_supported(work_dir: Path) -> tuple[np.ndarray, np.ndarray, list[int | None]]:
    all_triangles = np.load(work_dir / "navmesh-triangles.npy", mmap_mode="r")
    keep = np.load(work_dir / "nav-supported.npy", mmap_mode="r").astype(bool, copy=False)
    if all_triangles.ndim != 3 or all_triangles.shape[1:] != (3, 3) or len(keep) != len(all_triangles):
        raise ValueError("navmesh arrays do not match expected triangle/keep-mask shape")
    triangles = np.asarray(all_triangles[keep], dtype=np.float64)
    return triangles, keep, _model_ids_by_supported_index(work_dir, keep)


def compile_passage_sheets(
    work_dir: Path | str,
    *,
    region_id: str | None = None,
    edge_weld_m: float = 0.05,
    window_buffer_m: float = 3.0,
) -> dict[str, Any]:
    """Compile per-overlap 3D sheets; writes sidecar and QA beside navigation.json."""
    work_dir = Path(work_dir).resolve()
    if not math.isfinite(edge_weld_m) or edge_weld_m <= 0:
        raise ValueError("edge_weld_m must be finite and positive")
    if not math.isfinite(window_buffer_m) or window_buffer_m < 0:
        raise ValueError("window_buffer_m must be finite and nonnegative")
    navigation_path = work_dir / "navigation.json"
    navigation = json.loads(navigation_path.read_text(encoding="utf-8"))
    region_id = region_id or str(navigation.get("region", work_dir.name))
    triangles, keep, model_by_supported = _load_supported(work_dir)
    projected = sh.polygons(triangles[:, :, [0, 2]])
    tree = STRtree(projected)
    records: list[dict[str, Any]] = []
    totals = {"overlap_records": len(navigation.get("overlaps", [])), "components": 0,
              "ambiguous_single_sheet": 0, "empty_records": 0, "self_overlap_records": 0,
              "ambiguous_sheet_self_overlap_records": 0, "unused_window_triangles": 0,
              "core_components_dropped": 0,
              "source_triangles": 0, "core_triangles": 0, "retained_sheets": 0,
              "fallback_records_resolved": 0, "fallback_sheet_count": 0,
              "fallback_band_count": 0, "fallback_ambiguous_remaining": 0}

    for overlap in navigation.get("overlaps", []):
        overlap_id = int(overlap.get("id", len(records)))
        region, window = _record_window(overlap, window_buffer_m)
        # Geometry-index lookup returns supported-array indices, exactly the
        # indexing convention used by upper_triangles/lower_triangles.
        local_indices = np.asarray(tree.query(window, predicate="intersects"), dtype=np.int64)
        local_indices.sort()
        upper_ids = set(int(i) for i in overlap.get("upper_triangles", []))
        lower_ids = set(int(i) for i in overlap.get("lower_triangles", []))
        local_set = set(int(i) for i in local_indices)
        local_upper = sorted(upper_ids & local_set)
        local_lower = sorted(lower_ids & local_set)
        local_triangles = triangles[local_indices]
        local_polygons = projected[local_indices]
        component_groups, core_flags = _core_sheet_components(
            local_triangles, local_polygons, region, edge_weld_m
        )
        participating_ids = upper_ids | lower_ids
        side_models = {
            "upper": {model_by_supported[i] for i in local_upper if model_by_supported[i] is not None},
            "lower": {model_by_supported[i] for i in local_lower if model_by_supported[i] is not None},
        }
        self_overlap = bool(side_models["upper"] & side_models["lower"])
        if self_overlap:
            totals["self_overlap_records"] += 1

        sheets = []
        used_context = set()
        for sheet_id, (core_positions, render_positions) in enumerate(component_groups):
            source_ids = local_indices[np.asarray(render_positions, dtype=np.int64)]
            core_source_ids = local_indices[np.asarray(core_positions, dtype=np.int64)]
            used_context.update(render_positions)
            source_surfaces = triangles[source_ids]
            # Union only the component's projected source faces, then clip to
            # the exact region+buffer window. No gap-closing or dilation.
            face_polys = projected[source_ids]
            sheet_geometry = sh.intersection(sh.union_all(face_polys, grid_size=0.015), window)
            if sheet_geometry.is_empty or sheet_geometry.area <= 1e-8:
                continue
            overlap_core = sh.intersection(sh.union_all(projected[core_source_ids], grid_size=0.015), region)
            overlap_coverage_area = float(overlap_core.area)
            source_set = set(int(i) for i in source_ids)
            participates = bool(source_set & participating_ids)
            if overlap_coverage_area <= 0.05 and not participates:
                totals["core_components_dropped"] += 1
                continue
            packed = _packed(sheet_geometry)
            # Packed clipped geometry includes artificial window clip edges.
            # Keep outlines on the original component boundary only.
            physical_union = sh.union_all(face_polys)
            physical_lines = sh.intersection(physical_union.boundary, window)
            packed["outlines"] = [
                [[round(float(x), 3), round(float(z), 3)] for x, z in line.coords]
                for line in _line_parts(physical_lines)
            ]
            ys = source_surfaces[:, :, 1]
            models = sorted({model_by_supported[int(i)] for i in source_ids
                             if model_by_supported[int(i)] is not None})
            min_x, min_z, max_x, max_z = sheet_geometry.bounds
            internal_overlap_pairs = _sheet_self_overlap_pairs(source_surfaces, region)
            sheets.append({
                "id": sheet_id,
                "source_triangle_indices": [int(i) for i in source_ids],
                "source_side_ids": {
                    "upper": sorted(source_set & upper_ids),
                    "lower": sorted(source_set & lower_ids),
                },
                "source_model_ids": models,
                "geometry": packed,
                "surfaces_xyz": source_surfaces.tolist(),
                "min_y": float(ys.min()), "max_y": float(ys.max()),
                "mean_y": float(ys.mean()),
                "bounds": [float(min_x), float(min_z), float(max_x), float(max_z)],
                "overlap_coverage_area": overlap_coverage_area,
                "core_triangle_count": int(len(core_source_ids)),
                "context_triangle_count": int(len(source_ids) - len(core_source_ids)),
                "included_by_record_source": participates,
                "self_overlap_ambiguous": internal_overlap_pairs > 0,
                "self_overlap_pair_count": internal_overlap_pairs,
                "triangle_count": int(len(source_ids)),
            })

        pre_fallback_ambiguous = sum(sheet["self_overlap_ambiguous"] for sheet in sheets)
        fallback_sheet_count = fallback_band_count = 0
        if pre_fallback_ambiguous:
            expanded = []
            for sheet in sheets:
                if not sheet["self_overlap_ambiguous"]:
                    expanded.append(sheet)
                    continue
                bands = _fallback_bands(sheet, region)
                if bands:
                    expanded.extend(bands)
                    fallback_sheet_count += len(bands)
                    fallback_band_count += len(bands)
                else:
                    expanded.append(sheet)
            sheets = expanded
            for sheet_id, sheet in enumerate(sheets):
                sheet["id"] = sheet_id

        remaining_internal_overlap = any(sheet["self_overlap_ambiguous"] for sheet in sheets)
        if len(sheets) == 0:
            status = "empty"
            totals["empty_records"] += 1
        elif remaining_internal_overlap:
            status = "ambiguous_sheet_self_overlap"
            totals["ambiguous_sheet_self_overlap_records"] += 1
            totals["fallback_ambiguous_remaining"] += 1
        elif len(sheets) == 1:
            # One connected sheet cannot resolve a self-overlap into distinct
            # floors. Keep an explicit ambiguity marker instead of overstating.
            status = "ambiguous_single_sheet"
            totals["ambiguous_single_sheet"] += 1
        else:
            status = "resolved"
        if pre_fallback_ambiguous and not remaining_internal_overlap:
            totals["fallback_records_resolved"] += 1
        totals["fallback_sheet_count"] += fallback_sheet_count
        totals["fallback_band_count"] += fallback_band_count
        record = {
            "overlap_id": overlap_id,
            "sheets": sheets,
            "qa": {
                "status": status,
                "component_count": len(component_groups),
                "sheet_count": len(sheets),
                "local_source_triangle_count": int(len(local_indices)),
                "core_source_triangle_count": int(core_flags.sum()),
                "upper_source_triangle_count": len(local_upper),
                "lower_source_triangle_count": len(local_lower),
                "upper_model_ids": sorted(side_models["upper"]),
                "lower_model_ids": sorted(side_models["lower"]),
                "self_overlap": self_overlap,
                "sheet_internal_self_overlap": remaining_internal_overlap,
                "single_sheet_self_overlap_ambiguous": bool(self_overlap and len(sheets) == 1),
                "pre_fallback_ambiguous_sheet_count": int(pre_fallback_ambiguous),
                "fallback_sheet_count": fallback_sheet_count,
                "fallback_band_count": fallback_band_count,
                "fallback_source_proof": "Original XYZ source faces linearly clipped into 2 m Y bands and clipped to actual overlap core; outlines use the original component boundary intersected with the core; no band-cut walls.",
                "no_spatial_bridges": True,
            },
        }
        totals["components"] += len(component_groups)
        totals["source_triangles"] += len(local_indices)
        totals["core_triangles"] += int(core_flags.sum())
        totals["retained_sheets"] += len(sheets)
        totals["unused_window_triangles"] += int(len(local_indices) - len(used_context))
        records.append(record)

    report = {
        "schema": 1,
        "region": region_id,
        "source": {
            "navigation": "navigation.json",
            "supported_triangles": "navmesh-triangles.npy filtered by nav-supported.npy",
            "triangle_indices": "Indices into the filtered supported triangle array.",
        },
        "connectivity": {
            "method": "XYZ endpoint weld followed by exact shared full-edge adjacency.",
            "edge_weld_m": float(edge_weld_m),
            "window_buffer_m": float(window_buffer_m),
            "xz_only_connectivity": False,
            "bridge_gaps": False,
        },
        "records": records,
        "qa": totals,
    }
    output = work_dir / "passage-sheets.json"
    temp = output.with_suffix(output.suffix + ".tmp")
    temp.write_text(json.dumps(report, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    os.replace(temp, output)
    qa_path = work_dir / "passage-sheets-qa.json"
    qa_path.write_text(json.dumps({"schema": 1, "region": region_id, **totals,
                                   "records": [dict(id=r["overlap_id"], **r["qa"]) for r in records]},
                                  indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-id", required=True)
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--edge-weld-m", type=float, default=0.05)
    parser.add_argument("--window-buffer-m", type=float, default=3.0)
    args = parser.parse_args()
    work_dir = args.work_dir or ROOT / "work" / args.map_id
    report = compile_passage_sheets(work_dir, region_id=args.map_id,
                                    edge_weld_m=args.edge_weld_m,
                                    window_buffer_m=args.window_buffer_m)
    # No area labels or geometry details in stdout.
    print(json.dumps({"region": report["region"], **report["qa"]}))


if __name__ == "__main__":
    main()
