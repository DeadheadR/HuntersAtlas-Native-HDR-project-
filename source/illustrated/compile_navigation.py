"""Bake offline navigation, strict fog groups, art, and overlap meshes.

This compiler reads prepared per-map files and a verified base map package.
It writes an isolated candidate map package; it never edits installed player files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from pathlib import PurePosixPath
import shutil
import struct
import sys
import time
import zlib
from typing import Any, Iterable


PROJECT = Path(__file__).resolve().parent
REPO = PROJECT.parents[1]
_deps = os.environ.get("ATLAS_PYTHON_DEPS")
if _deps and str(Path(_deps).resolve()) not in sys.path:
    sys.path.insert(0, str(Path(_deps).resolve()))

import numpy as np
import shapely as sh
from shapely.geometry import LineString, Point, Polygon, box
from shapely.prepared import prep
from shapely.strtree import STRtree


DEFAULT_BASE = Path(os.environ.get("ATLAS_BASE_MAPS", PROJECT / "maps-baked"))
MAX_RAW_BYTES = 256 * 1024 * 1024
VERTEX = struct.Struct("<4fI")
U32 = struct.Struct("<I")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                        allow_nan=False) + "\n").encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def _msg_len(length: int, fix_base: int, fix_limit: int,
             code8: int, code16: int, code32: int) -> bytes:
    if length < fix_limit:
        return bytes([fix_base | length])
    if length <= 0xFF:
        return bytes([code8, length])
    if length <= 0xFFFF:
        return bytes([code16]) + struct.pack(">H", length)
    if length <= 0xFFFFFFFF:
        return bytes([code32]) + struct.pack(">I", length)
    raise ValueError("MessagePack container too large")


def msgpack(value: Any) -> bytes:
    """Encode JSON-shaped values plus Python bytes without a runtime dependency."""
    if value is None:
        return b"\xc0"
    if value is False:
        return b"\xc2"
    if value is True:
        return b"\xc3"
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        if len(raw) <= 0xFF:
            return b"\xc4" + bytes([len(raw)]) + raw
        if len(raw) <= 0xFFFF:
            return b"\xc5" + struct.pack(">H", len(raw)) + raw
        return b"\xc6" + struct.pack(">I", len(raw)) + raw
    if isinstance(value, str):
        raw = value.encode("utf-8")
        if len(raw) < 32:
            return bytes([0xA0 | len(raw)]) + raw
        if len(raw) <= 0xFF:
            return b"\xd9" + bytes([len(raw)]) + raw
        if len(raw) <= 0xFFFF:
            return b"\xda" + struct.pack(">H", len(raw)) + raw
        return b"\xdb" + struct.pack(">I", len(raw)) + raw
    if isinstance(value, int):
        if 0 <= value <= 0x7F:
            return bytes([value])
        if -32 <= value < 0:
            return bytes([value & 0xFF])
        if value >= 0:
            for marker, fmt, maximum in ((0xCC, ">B", 0xFF), (0xCD, ">H", 0xFFFF),
                                         (0xCE, ">I", 0xFFFFFFFF), (0xCF, ">Q", 0xFFFFFFFFFFFFFFFF)):
                if value <= maximum:
                    return bytes([marker]) + struct.pack(fmt, value)
        else:
            for marker, fmt, minimum in ((0xD0, ">b", -0x80), (0xD1, ">h", -0x8000),
                                          (0xD2, ">i", -0x80000000), (0xD3, ">q", -0x8000000000000000)):
                if value >= minimum:
                    return bytes([marker]) + struct.pack(fmt, value)
        raise ValueError("MessagePack integer out of range")
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite MessagePack float")
        return b"\xcb" + struct.pack(">d", value)
    if isinstance(value, (list, tuple)):
        head = _msg_len(len(value), 0x90, 16, 0xDC, 0xDC, 0xDD)
        if len(value) >= 16:
            head = (b"\xdc" + struct.pack(">H", len(value)) if len(value) <= 0xFFFF
                    else b"\xdd" + struct.pack(">I", len(value)))
        return head + b"".join(msgpack(item) for item in value)
    if isinstance(value, dict):
        length = len(value)
        if length < 16:
            head = bytes([0x80 | length])
        elif length <= 0xFFFF:
            head = b"\xde" + struct.pack(">H", length)
        else:
            head = b"\xdf" + struct.pack(">I", length)
        return head + b"".join(msgpack(key) + msgpack(item) for key, item in value.items())
    raise TypeError(f"Unsupported MessagePack type: {type(value).__name__}")


def a3z_pack(value: Any) -> bytes:
    raw = msgpack(value)
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError(f"navigation payload exceeds {MAX_RAW_BYTES} bytes")
    return b"A3Z1" + U32.pack(len(raw)) + zlib.compress(raw, level=9)


def verify_maps_tree(root: Path, *, check_package_pin: bool = True) -> dict[str, Any]:
    index_path = root / "atlas2-index.json"
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)
    index_hash = hashlib.sha256(index_bytes).hexdigest()
    package_manifest_path = root.parent / "manifest.json"
    if check_package_pin and package_manifest_path.is_file():
        package_manifest = json.loads(package_manifest_path.read_text(encoding="utf-8"))
        declared = package_manifest.get("compact_maps", {}).get("index_sha256")
        if declared != index_hash:
            raise ValueError("production maps-baked index does not match root package manifest")
    if index.get("schema") != 1 or index.get("format") != "compiled-vector-v1" or len(index.get("areas", [])) != 16:
        raise ValueError("maps-baked index must describe the 16 supported compiled-vector areas")
    checked = 0
    for row in index["areas"]:
        area = row.get("area", "")
        if not isinstance(area, str) or not area.startswith("Area") or len(area) != 6:
            raise ValueError("invalid AreaNN entry in maps-baked index")
        area_dir = root / area
        manifest_path = area_dir / "manifest.json"
        manifest_bytes = manifest_path.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != row.get("manifest_sha256"):
            raise ValueError(f"area manifest hash mismatch: {area}")
        manifest = json.loads(manifest_bytes)
        if manifest.get("schema") != 4 or manifest.get("region_id") != row.get("region_id"):
            raise ValueError(f"area manifest identity mismatch: {area}")
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError(f"area files table is missing: {area}")
        for name, digest in files.items():
            relative = PurePosixPath(str(name))
            if len(relative.parts) != 1 or relative.name in (".", ".."):
                raise ValueError(f"unsafe area file path: {name}")
            path = area_dir / relative.name
            if not path.is_file() or sha256(path) != digest:
                raise ValueError(f"area file hash mismatch: {area}/{name}")
            checked += 1
    return {"index": index, "index_sha256": index_hash, "checked_area_files": checked}


def polygon_parts(geometry: Any) -> Iterable[Polygon]:
    if geometry is None or geometry.is_empty:
        return
    if geometry.geom_type == "Polygon":
        yield geometry
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from polygon_parts(part)


def line_parts(geometry: Any) -> Iterable[LineString]:
    if geometry is None or geometry.is_empty:
        return
    if geometry.geom_type in ("LineString", "LinearRing"):
        yield LineString(geometry.coords)
    elif hasattr(geometry, "geoms"):
        for part in geometry.geoms:
            yield from line_parts(part)


def subdivide_line(line: LineString, max_length: float = 1.0) -> Iterable[LineString]:
    length = float(line.length)
    pieces = max(1, int(math.ceil(length / max_length)))
    for index in range(pieces):
        a = line.interpolate(index / pieces, normalized=True)
        b = line.interpolate((index + 1) / pieces, normalized=True)
        if a.distance(b) > 1e-8:
            yield LineString((a.coords[0], b.coords[0]))


def msgpack_mesh_empty() -> dict[str, Any]:
    return {"vertices": b"", "indices": b"", "groups": []}


class MeshBuilder:
    def __init__(self) -> None:
        self.vertices = bytearray()
        self.indices = bytearray()
        self.groups: list[list[Any]] = []
        self.vertex_count = 0

    def _group(self, required: Iterable[int]) -> None:
        ids = sorted(set(int(value) for value in required))
        if any(value < -1 or value > 255 for value in ids):
            raise ValueError(f"invalid fog requirement IDs: {ids}")
        if self.groups and self.groups[-1][2] == ids:
            return
        self.groups.append([len(self.indices) // 4, 0, ids])

    def _vertex(self, x: float, z: float, u: float, v: float, color: int = 0xFFFFFFFF) -> int:
        values = (float(x), -float(z), float(u), float(v))
        if not all(math.isfinite(value) for value in values):
            raise ValueError("non-finite mesh vertex")
        self.vertices.extend(VERTEX.pack(*values, color))
        index = self.vertex_count
        self.vertex_count += 1
        return index

    def triangle(self, points: Iterable[tuple[float, float, float, float]],
                 required: Iterable[int]) -> None:
        rows = list(points)
        if len(rows) != 3:
            raise ValueError("mesh triangle requires three vertices")
        self._group(required)
        base = self.vertex_count
        for x, z, u, v in rows:
            self._vertex(x, z, u, v)
        for index in (base, base + 1, base + 2):
            self.indices.extend(U32.pack(index))
        self.groups[-1][1] += 3

    def line(self, a: tuple[float, float], b: tuple[float, float],
             required: Iterable[int]) -> None:
        x, z = map(float, a)
        xx, zz = map(float, b)
        dx, dz = xx - x, -(zz - z)
        length = math.hypot(dx, dz)
        if length < 1e-8:
            return
        self._group(required)
        nx, nz = -dz / length, dx / length
        base = self.vertex_count
        for px, pz in ((x, z), (xx, zz)):
            for k in range(4):
                sign = 1.0 if k < 2 else -1.0
                color = 0x00FFFFFF if k in (0, 3) else 0xFFFFFFFF
                self._vertex(px, pz, sign * nx, sign * nz, color)
        for k in range(3):
            for index in (k, k + 4, k + 5, k, k + 5, k + 1):
                self.indices.extend(U32.pack(base + index))
        self.groups[-1][1] += 18

    def finish(self) -> dict[str, Any]:
        if len(self.vertices) > MAX_RAW_BYTES or len(self.indices) > MAX_RAW_BYTES:
            raise ValueError("mesh buffer exceeds runtime bound")
        return {"vertices": bytes(self.vertices), "indices": bytes(self.indices),
                "groups": self.groups}


def _cross(a: tuple[float, float], b: tuple[float, float],
           p: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _barycentric_xz(triangle: np.ndarray, x: float, z: float) -> tuple[float, float, float] | None:
    a, b, c = triangle[:, [0, 2]]
    den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(float(den)) < 1e-10:
        return None
    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (z - c[1])) / den
    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (z - c[1])) / den
    w = 1.0 - u - v
    return float(u), float(v), float(w)


def _closest_on_segment(p: tuple[float, float], a: tuple[float, float],
                        b: tuple[float, float]) -> tuple[float, float, float]:
    dx, dz = b[0] - a[0], b[1] - a[1]
    denom = dx * dx + dz * dz
    t = 0.0 if denom <= 1e-16 else max(0.0, min(1.0, ((p[0]-a[0])*dx+(p[1]-a[1])*dz)/denom))
    return a[0] + t * dx, a[1] + t * dz, t


class SurfaceIndex:
    """Closest supported navmesh projection in XZ, returning its source Y."""
    def __init__(self, triangles: np.ndarray) -> None:
        self.triangles = np.asarray(triangles, dtype=np.float64)
        if self.triangles.ndim != 3 or self.triangles.shape[1:] != (3, 3) or not len(self.triangles):
            raise ValueError("supported navmesh must be a non-empty Nx3x3 array")
        self.geometries = []
        self.geometry_triangle_ids = []
        for index, triangle in enumerate(self.triangles):
            points = [tuple(map(float, point)) for point in triangle[:, [0, 2]]]
            polygon = Polygon(points)
            if polygon.is_empty or polygon.area <= 1e-12:
                # Vertical/projected-degenerate faces still supply exact edge
                # support to nearby points; keep them in the same spatial index.
                geometry = LineString((points[0], points[1], points[2]))
            else:
                geometry = polygon
            if not geometry.is_empty:
                self.geometries.append(geometry)
                self.geometry_triangle_ids.append(index)
        if not self.geometries:
            raise ValueError("supported navmesh has no non-empty XZ projections")
        self.tree = STRtree(self.geometries)
        self.geometry_triangle_ids = np.asarray(self.geometry_triangle_ids, dtype=np.int64)
        self.cache: dict[tuple[int, int], tuple[float | None, float, bool]] = {}

    @staticmethod
    def _project(triangle: np.ndarray, x: float, z: float) -> tuple[float, float]:
        bary = _barycentric_xz(triangle, x, z)
        if bary is not None and min(bary) >= -1e-8:
            return float(np.dot(np.asarray(bary), triangle[:, 1])), 0.0
        points = triangle[:, [0, 2]]
        candidates = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            qx, qz, t = _closest_on_segment((x, z), tuple(points[i]), tuple(points[j]))
            y = float(triangle[i, 1] + t * (triangle[j, 1] - triangle[i, 1]))
            candidates.append((math.hypot(qx - x, qz - z), y))
        distance, y = min(candidates, key=lambda item: item[0])
        return y, distance

    def at(self, x: float, z: float) -> tuple[float | None, float, bool]:
        key = (round(float(x) * 10000), round(float(z) * 10000))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        point = Point(float(x), float(z))
        # First collect every face whose projected polygon contains the query.
        # This is exact at boundaries and handles arbitrary triangle sizes;
        # centroid-neighbor caps can miss large faces or stacked surfaces.
        geometry_ids = np.asarray(self.tree.query(point, predicate="intersects"), dtype=np.int64)
        if geometry_ids.size:
            best = 0.0
        else:
            nearest = np.asarray(self.tree.query_nearest(point, all_matches=True), dtype=np.int64).reshape(-1)
            if not nearest.size:
                raise RuntimeError("STRtree found no nearest projected navmesh face")
            best = min(float(point.distance(self.geometries[int(index)])) for index in nearest)
            # Include all geometries tied within the same tolerance used for
            # height ambiguity, not just the one nearest item returned first.
            geometry_ids = np.asarray(self.tree.query(
                point, predicate="dwithin", distance=best + 1e-4), dtype=np.int64)
        ids = self.geometry_triangle_ids[geometry_ids]
        values = []
        for index in ids:
            y, distance = self._project(self.triangles[index], x, z)
            values.append((distance, y))
        best = min(row[0] for row in values)
        close = [row for row in values if row[0] <= best + 1e-4]
        heights = [row[1] for row in close]
        ambiguous = bool(heights and max(heights) - min(heights) > 0.25)
        result = ((None if ambiguous else float(np.median(heights))), float(best), ambiguous)
        self.cache[key] = result
        return result

    def plane_for_triangle(self, points: list[tuple[float, float]],
                           max_distance: float) -> tuple[tuple[float, float, float] | None, list[float], bool]:
        heights, distances = [], []
        ambiguous = False
        for x, z in points:
            y, distance, uncertain = self.at(x, z)
            if y is None or distance > max_distance:
                ambiguous = True
                heights.append(float("nan"))
            else:
                heights.append(y)
            distances.append(distance)
            ambiguous = ambiguous or uncertain
        if ambiguous or len(points) < 3:
            return None, heights, ambiguous
        matrix = np.asarray([[x, z, 1.0] for x, z in points[:3]], dtype=np.float64)
        try:
            coeff = np.linalg.solve(matrix, np.asarray(heights[:3], dtype=np.float64))
        except np.linalg.LinAlgError:
            return None, heights, True
        plane = tuple(map(float, coeff))
        residuals = [abs((plane[0]*x + plane[1]*z + plane[2]) - y)
                     for (x, z), y in zip(points, heights)]
        if max(residuals, default=0.0) > 0.25:
            return None, heights, True
        return plane, heights, False


def _clip_ring(points: list[tuple[float, float]],
               evaluate: Any, keep_positive: bool) -> list[tuple[float, float]]:
    if not points:
        return []
    result: list[tuple[float, float]] = []
    previous = points[-1]
    previous_value = float(evaluate(previous))
    previous_inside = previous_value >= -1e-10 if keep_positive else previous_value <= 1e-10
    for current in points:
        current_value = float(evaluate(current))
        current_inside = current_value >= -1e-10 if keep_positive else current_value <= 1e-10
        if current_inside != previous_inside:
            denom = previous_value - current_value
            if abs(denom) > 1e-20:
                t = previous_value / denom
                result.append((previous[0] + t*(current[0]-previous[0]),
                              previous[1] + t*(current[1]-previous[1])))
        if current_inside:
            result.append(current)
        previous, previous_value, previous_inside = current, current_value, current_inside
    clean: list[tuple[float, float]] = []
    for point in result:
        if not clean or math.dist(clean[-1], point) > 1e-8:
            clean.append(point)
    if len(clean) > 1 and math.dist(clean[0], clean[-1]) <= 1e-8:
        clean.pop()
    return clean


def halfplane(bounds: tuple[float, float, float, float],
              coeff: tuple[float, float, float], keep_positive: bool) -> Any:
    minx, minz, maxx, maxz = bounds
    margin = max(maxx - minx, maxz - minz, 1.0) * 3 + 100.0
    corners = [(minx-margin, minz-margin), (maxx+margin, minz-margin),
               (maxx+margin, maxz+margin), (minx-margin, maxz+margin)]
    a, b, c = coeff
    ring = _clip_ring(corners, lambda p: a*p[0] + b*p[1] + c, keep_positive)
    if len(ring) < 3:
        return Polygon()
    return Polygon(ring)


def clip_y(geometry: Any, plane: tuple[float, float, float],
           low: float, high: float, margin: float = 0.0) -> Any:
    if geometry.is_empty:
        return geometry
    a, b, c = plane
    minx, minz, maxx, maxz = geometry.bounds
    if math.hypot(a, b) < 1e-12:
        y = c
        return geometry if low + margin <= y <= high - margin else Polygon()
    result = geometry
    if low > -1e8:
        result = result.intersection(halfplane(result.bounds, (a, b, c - (low + margin)), True))
    if not result.is_empty and high < 1e8:
        result = result.intersection(halfplane(result.bounds, (a, b, c - (high - margin)), False))
    return result


def rule_shape(rule: dict[str, Any], world_bounds: tuple[float, float, float, float]) -> Any:
    shape = box(*world_bounds)
    if "bounds" in rule:
        b = rule["bounds"]
        if len(b) != 4:
            raise ValueError("features.json reveal bounds must have four coordinates")
        shape = shape.intersection(box(float(b[0]), float(b[1]), float(b[2]), float(b[3])))
    if "centre" in rule:
        center = rule["centre"]
        if len(center) < 3:
            raise ValueError("features.json reveal centre must contain XYZ")
        radius = float(rule.get("radius", 0.0))
        if radius < 0 or not math.isfinite(radius):
            raise ValueError("invalid reveal radius")
        circle = Point(float(center[0]), float(center[2])).buffer(radius, quad_segs=512)
        shape = shape.intersection(circle)
    if "triangles" in rule:
        triangles = []
        for t in rule["triangles"]:
            if len(t) != 6:
                raise ValueError("feature reveal triangle must be three XZ pairs")
            poly = Polygon([(float(t[i]), float(t[i+1])) for i in (0, 2, 4)])
            if not poly.is_empty and poly.area > 1e-10:
                triangles.append(poly)
        tri_shape = sh.union_all(triangles) if triangles else Polygon()
        shape = shape.intersection(tri_shape)
    return shape


def region_id(feature: dict[str, Any], x: float, y: float, z: float) -> int:
    if bool(feature.get("always_visible", False)):
        return -2
    for index, rule in enumerate(feature.get("reveal_regions", [])):
        if y < float(rule.get("min_y", -1e9)) or y > float(rule.get("max_y", 1e9)):
            continue
        if "bounds" in rule:
            b = rule["bounds"]
            if x < b[0] or z < b[1] or x > b[2] or z > b[3]:
                continue
        if "centre" in rule:
            p = rule["centre"]
            radius = float(rule.get("radius", 0.0))
            if (x - p[0])**2 + (z - p[2])**2 > radius**2:
                continue
        if "triangles" in rule:
            hit = False
            for t in rule["triangles"]:
                a = (float(t[0]), float(t[1]))
                b = (float(t[2]), float(t[3]))
                c = (float(t[4]), float(t[5]))
                p = (x, z)
                cross = (_cross(a, b, p), _cross(b, c, p), _cross(c, a, p))
                if (min(cross) >= 0.0) or (max(cross) <= 0.0):
                    hit = True
                    break
            if not hit:
                continue
        return index
    return -1


class RegionRules:
    def __init__(self, feature: dict[str, Any], bounds: tuple[float, float, float, float]) -> None:
        self.feature = feature
        self.always = bool(feature.get("always_visible", False))
        self.rules = feature.get("reveal_regions", [])
        if not isinstance(self.rules, list) or len(self.rules) > 256:
            raise ValueError("feature reveal region count is invalid")
        self.regions = []
        for rule in self.rules:
            if not isinstance(rule, dict):
                raise ValueError("feature reveal rule must be an object")
            shape = rule_shape(rule, bounds)
            self.regions.append((shape, float(rule.get("min_y", -1e9)),
                                 float(rule.get("max_y", 1e9)),
                                 prep(shape) if not shape.is_empty else None))

    def clip(self, geometry: Any, plane: tuple[float, float, float],
             *, margin: float = 0.0) -> list[tuple[Any, list[int]]]:
        if geometry.is_empty or geometry.area <= 1e-10:
            return []
        if self.always:
            return [(geometry, [])]
        remaining = geometry
        output = []
        for index, (shape, low, high, prepared) in enumerate(self.regions):
            if remaining.is_empty:
                break
            if shape.is_empty or not remaining.intersects(shape):
                continue
            coordinates = list(remaining.exterior.coords) if remaining.geom_type == "Polygon" else []
            if coordinates and prepared is not None:
                heights = [eval_plane(plane, float(x), float(z)) for x, z in coordinates[:-1]]
                if (min(heights) >= low + margin and max(heights) <= high - margin
                        and prepared.covers(remaining)):
                    # A full first-rule hit requires no overlay or retriangulation.
                    output.append((remaining, [index]))
                    remaining = Polygon()
                    break
            candidate = remaining.intersection(shape)
            candidate = clip_y(candidate, plane, low, high, margin)
            if candidate.is_empty or candidate.area <= 1e-10:
                continue
            output.append((candidate, [index]))
            remaining = sh.difference(remaining, candidate)
        if not remaining.is_empty and remaining.area > 1e-10:
            output.append((remaining, [-1]))
        return output


def triangulate(geometry: Any) -> Iterable[list[tuple[float, float]]]:
    for poly in polygon_parts(geometry):
        if poly.area <= 1e-10:
            continue
        result = sh.constrained_delaunay_triangles(poly)
        for tri in polygon_parts(result):
            coords = list(tri.exterior.coords)[:-1]
            if len(coords) != 3 or tri.area <= 1e-10:
                continue
            yield [(float(x), float(z)) for x, z in coords]


def plane_from_triangle(triangle: np.ndarray) -> tuple[float, float, float]:
    points = [(float(row[0]), float(row[2])) for row in triangle]
    ys = [float(row[1]) for row in triangle]
    matrix = np.asarray([[x, z, 1.0] for x, z in points], dtype=np.float64)
    coeff = np.linalg.solve(matrix, np.asarray(ys, dtype=np.float64))
    return tuple(map(float, coeff))


def eval_plane(plane: tuple[float, float, float], x: float, z: float) -> float:
    return plane[0] * x + plane[1] * z + plane[2]


def mesh_from_nav_triangle(geometry: Any, plane: tuple[float, float, float],
                           required: list[int], builder: MeshBuilder) -> int:
    count = 0
    for xyz in triangulate(geometry):
        builder.triangle([(x, z, 0.0, 0.0) for x, z in xyz], required)
        count += 1
    return count


def packed_triangles(packed: dict[str, Any]) -> Iterable[list[tuple[float, float]]]:
    for t in packed.get("triangles", []):
        if len(t) != 6 or not all(math.isfinite(float(v)) for v in t):
            raise ValueError("packed navigation triangle is malformed")
        yield [(float(t[i]), float(t[i+1])) for i in (0, 2, 4)]


def compile_surface(nav: dict[str, Any], rules: RegionRules,
                    supported: np.ndarray) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    ground_builder, outline_builder, fringe_builder = MeshBuilder(), MeshBuilder(), MeshBuilder()
    triangles_seen = 0
    ground_output = 0
    source_area = 0.0
    assigned_area = 0.0
    max_area_error = 0.0
    group_counts: dict[str, int] = {}
    for triangle in supported:
        points = [(float(p[0]), float(p[2])) for p in triangle]
        source = Polygon(points)
        if source.is_empty or source.area <= 1e-10:
            continue
        plane = plane_from_triangle(triangle)
        triangles_seen += 1
        source_area += float(source.area)
        clipped = rules.clip(source, plane)
        clipped_area = sum(float(geometry.area) for geometry, _ in clipped)
        delta = abs(float(source.area) - clipped_area)
        max_area_error = max(max_area_error, delta)
        if delta > max(1e-8, float(source.area) * 1e-9):
            raise ValueError(f"fog clipping changed supported source area by {delta:.9g} m^2")
        assigned_area += clipped_area
        for geometry, required in clipped:
            count = mesh_from_nav_triangle(geometry, plane, required, ground_builder)
            ground_output += count
            key = ",".join(map(str, required)) or "always"
            group_counts[key] = group_counts.get(key, 0) + count

    # Use the unioned authored nav footprint so adjacent source triangle seams
    # never become visible outlines.
    chunks = []
    for offset in range(0, len(supported), 4000):
        tri = supported[offset:offset + 4000, :, :][:, :, [0, 2]]
        if len(tri):
            chunks.append(sh.union_all(sh.polygons(tri), grid_size=0.015))
    footprint = sh.make_valid(sh.union_all(chunks)) if chunks else Polygon()
    if footprint.is_empty:
        raise ValueError("supported navigation footprint is empty")
    bounds = tuple(map(float, footprint.bounds))

    def closest_y(x: float, z: float) -> tuple[float | None, float, bool]:
        # Local index is cached and shared across fringe, outline and artwork.
        return surface_index.at(x, z)

    surface_index = SurfaceIndex(supported)
    for line in line_parts(footprint.boundary):
        for segment in subdivide_line(line):
            if rules.always:
                outline_builder.line(tuple(segment.coords[0]), tuple(segment.coords[-1]), [])
                continue
            remaining = segment
            for region_index, (region_shape, low, high, _) in enumerate(rules.regions):
                if remaining.is_empty or region_shape.is_empty or not remaining.intersects(region_shape):
                    continue
                candidate = remaining.intersection(region_shape)
                assigned = []
                for fragment in line_parts(candidate):
                    for small in subdivide_line(fragment):
                        coords = list(small.coords)
                        samples = [(float(coords[0][0] + (coords[-1][0]-coords[0][0])*t),
                                    float(coords[0][1] + (coords[-1][1]-coords[0][1])*t))
                                   for t in (0.0, .25, .5, .75, 1.0)]
                        sample_regions = []
                        for x, z in samples:
                            y, distance, ambiguous = closest_y(x, z)
                            if y is None or distance > 0.1 or ambiguous:
                                sample_regions.append(-1)
                            else:
                                sample_regions.append(region_id(rules.feature, x, y, z))
                        if all(value == region_index for value in sample_regions):
                            outline_builder.line(tuple(coords[0]), tuple(coords[-1]), [region_index])
                            assigned.append(small)
                if assigned:
                    remaining = sh.difference(remaining, sh.union_all(assigned))
            for fragment in line_parts(remaining):
                for small in subdivide_line(fragment):
                    coords = list(small.coords)
                    outline_builder.line(tuple(coords[0]), tuple(coords[-1]), [-1])

    fringe_source = nav.get("fringe", {})
    fringe_input = 0
    fringe_visible = 0
    fringe_uncertain = 0
    outer_limit = 16.0
    for flat in fringe_source.get("triangles", []):
        if len(flat) != 6:
            raise ValueError("fringe triangle malformed")
        xyz = [(float(flat[i]), float(flat[i+1])) for i in (0, 2, 4)]
        poly = Polygon(xyz)
        if poly.area <= 1e-10:
            continue
        xy = [(float(x), float(z)) for x, z in xyz]
        samples = xy + [(float(poly.centroid.x), float(poly.centroid.y))]
        plane, _, ambiguous = surface_index.plane_for_triangle(samples, 1.3)
        fringe_input += 1
        if plane is None or ambiguous:
            required = [-1]
            # Preserve unknown fringe only for fog-off display. It never leaks
            # into discovered-only map rendering.
            fringe_builder.triangle([(x, z, 0, 0) for x, z in xyz], required)
            fringe_uncertain += 1
            continue
        for geometry, required in rules.clip(poly, plane, margin=0.25):
            fringe_visible += mesh_from_nav_triangle(geometry, plane, required, fringe_builder)

    report = {"supported_source_triangles": int(len(supported)),
              "ground_source_triangles_processed": triangles_seen,
              "ground_output_triangles": ground_output,
              "ground_source_projected_area": source_area,
              "ground_grouped_projected_area": assigned_area,
              "ground_group_area_delta": abs(source_area - assigned_area),
              "ground_max_per_triangle_area_delta": max_area_error,
              "ground_area_partition_valid": abs(source_area - assigned_area) <= max(1e-6, source_area * 1e-9),
              "ground_groups_by_requirements": group_counts,
              "footprint_area": float(footprint.area),
              "fringe_source_triangles": fringe_input,
              "fringe_clipped_output_triangles": fringe_visible,
              "fringe_uncertain_triangles": fringe_uncertain,
              "outline_segments": int(sum(group[1] for group in outline_builder.groups) // 18)}
    return (ground_builder.finish(), outline_builder.finish(), fringe_builder.finish(), report)


def _sample_requirements(points: list[tuple[float, float]], feature: dict[str, Any],
                         index: SurfaceIndex, max_distance: float = 1.0) -> list[int]:
    result: set[int] = set()
    for x, z in points:
        y, distance, ambiguous = index.at(x, z)
        if y is None or distance > max_distance or ambiguous:
            result.add(-1)
            continue
        region = region_id(feature, x, y, z)
        if region != -2:
            result.add(region)
    return sorted(result)


def load_passage_sheets(path: Path, nav: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    """Load optional passage-sheet analysis keyed by source overlap ID.

    Source envelope is {schema: 1, region, records: [{overlap_id, sheets: [...]}]}.
    The source uses snake_case for surfaces_xyz; normalize it to the runtime's
    established surfacesXYZ spelling while retaining the original source field.
    """
    if not path.is_file():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(document, dict):
        if document.get("schema") != 1 or document.get("region") != nav.get("region"):
            raise ValueError(f"{path}: passage-sheet schema or region mismatch")
        rows = document.get("records", [])
    else:
        rows = document
    if not isinstance(rows, list):
        raise ValueError(f"{path}: expected an overlaps array")
    known_ids = {int(row["id"]) for row in nav.get("overlaps", []) if "id" in row}
    result: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict) or "overlap_id" not in row or not isinstance(row.get("sheets"), list):
            raise ValueError(f"{path}: each record needs overlap_id and sheets[]")
        overlap_id = int(row["overlap_id"])
        if overlap_id not in known_ids:
            raise ValueError(f"{path}: unknown overlap id {overlap_id}")
        if overlap_id in result:
            raise ValueError(f"{path}: duplicate overlap id {overlap_id}")
        for sheet in row["sheets"]:
            if not isinstance(sheet, dict) or not isinstance(sheet.get("geometry"), dict):
                raise ValueError(f"{path}: sheet geometry is missing for overlap {overlap_id}")
            surfaces = np.asarray(sheet.get("surfaces_xyz", sheet.get("surfacesXYZ", [])), dtype=np.float64)
            if surfaces.size == 0 or surfaces.size % 9:
                raise ValueError(f"{path}: sheet surfaces_xyz must contain source XYZ triangles")
        result[overlap_id] = []
        for sheet in row["sheets"]:
            normalized = dict(sheet)
            normalized["surfacesXYZ"] = sheet.get("surfaces_xyz", sheet.get("surfacesXYZ"))
            result[overlap_id].append(normalized)
    return result


def compile_overlap_meshes(nav: dict[str, Any], feature: dict[str, Any],
                           global_index: SurfaceIndex,
                           footprint: Any,
                           external_sheets: dict[int, list[dict[str, Any]]] | None = None
                           ) -> tuple[list[dict[str, Any]], dict[str, int]]:
    output = []
    counts = {"overlap_masks": 0, "upper_fill": 0, "lower_fill": 0,
              "upper_edge_segments": 0, "lower_edge_segments": 0,
              "passage_sheet_fill": 0, "passage_sheet_edge_segments": 0}
    for overlap in nav.get("overlaps", []):
        record = dict(overlap)
        mask_builder, upper_builder, lower_builder = MeshBuilder(), MeshBuilder(), MeshBuilder()
        upper_edge_builder, lower_edge_builder = MeshBuilder(), MeshBuilder()
        upper_surfaces = np.asarray(overlap.get("upper_surfaces", []), dtype=np.float64)
        lower_surfaces = np.asarray(overlap.get("lower_surfaces", []), dtype=np.float64)
        if upper_surfaces.size:
            upper_surfaces = upper_surfaces.reshape((-1, 3, 3))
        else:
            upper_surfaces = np.empty((0, 3, 3), dtype=np.float64)
        if lower_surfaces.size:
            lower_surfaces = lower_surfaces.reshape((-1, 3, 3))
        else:
            lower_surfaces = np.empty((0, 3, 3), dtype=np.float64)
        upper_index = SurfaceIndex(upper_surfaces) if len(upper_surfaces) else None
        lower_index = SurfaceIndex(lower_surfaces) if len(lower_surfaces) else None

        def add_fills(packed: dict[str, Any], target: MeshBuilder,
                      local_index: SurfaceIndex | None, field: str) -> None:
            nonlocal counts
            for points in packed_triangles(packed):
                poly = Polygon(points)
                if poly.area <= 1e-10:
                    continue
                center = (float(poly.centroid.x), float(poly.centroid.y))
                samples = points + [center]
                required = _sample_requirements(samples, feature, local_index, 0.75) if local_index else [-1]
                for tri in triangulate(poly):
                    target.triangle([(x, z, 0, 0) for x, z in tri], required)
                    counts[field] += 1

        # The mask is gated by both actual walkable surfaces. This is stricter
        # than centroid-only XY sampling and prevents fogged floors leaking.
        mask_geom = overlap.get("overlap_geometry", {})
        for points in packed_triangles(mask_geom):
            poly = Polygon(points)
            if poly.area <= 1e-10:
                continue
            center = (float(poly.centroid.x), float(poly.centroid.y))
            sample_points = points + [center]
            inside_ground = [footprint.covers(Point(x, z)) for x, z in sample_points]
            req = set(_sample_requirements(sample_points, feature, global_index, 0.75))
            if not all(inside_ground):
                req.add(-1)
            if upper_index:
                req.update(_sample_requirements(sample_points, feature, upper_index, 0.75))
            if lower_index:
                req.update(_sample_requirements(sample_points, feature, lower_index, 0.75))
            required = sorted(req)
            for tri in triangulate(poly):
                mask_builder.triangle([(x, z, 0, 0) for x, z in tri], required)
                counts["overlap_masks"] += 1

        upper_geometry = overlap.get("geometry", {})
        lower_geometry = overlap.get("lower_geometry", {})
        add_fills(upper_geometry, upper_builder, upper_index, "upper_fill")
        add_fills(lower_geometry, lower_builder, lower_index, "lower_fill")

        def add_edges(packed: dict[str, Any], target: MeshBuilder,
                      local_index: SurfaceIndex | None, field: str) -> None:
            for ring in packed.get("outlines", []):
                if len(ring) < 2:
                    continue
                for a, b in zip(ring, ring[1:]):
                    pa, pb = (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
                    middle = ((pa[0]+pb[0])*.5, (pa[1]+pb[1])*.5)
                    sample = [pa, middle, pb]
                    required = (_sample_requirements(sample, feature, local_index, 0.75)
                                if local_index else [-1])
                    target.line(pa, pb, required)
                    counts[field] += 1

        add_edges(upper_geometry, upper_edge_builder, upper_index, "upper_edge_segments")
        add_edges(lower_geometry, lower_edge_builder, lower_index, "lower_edge_segments")
        packed_sheets = []
        sheet_rows = (external_sheets or {}).get(int(overlap.get("id", -1)),
                                                   overlap.get("sheets", []))
        for sheet in sheet_rows:
            sheet_record = dict(sheet)
            surfaces = np.asarray(sheet.get("surfacesXYZ", []), dtype=np.float64)
            if surfaces.size:
                surfaces = surfaces.reshape((-1, 3, 3))
                sheet_index = SurfaceIndex(surfaces)
            else:
                sheet_index = None
            sheet_geometry = sheet.get("geometry", {})
            sheet_mesh_builder = MeshBuilder()
            sheet_edge_builder = MeshBuilder()
            for points in packed_triangles(sheet_geometry):
                poly = Polygon(points)
                if poly.area <= 1e-10:
                    continue
                samples = points + [(float(poly.centroid.x), float(poly.centroid.y))]
                required = (_sample_requirements(samples, feature, sheet_index, .75)
                            if sheet_index else [-1])
                for tri in triangulate(poly):
                    sheet_mesh_builder.triangle([(x, z, 0, 0) for x, z in tri], required)
                    counts["passage_sheet_fill"] += 1
            for ring in sheet_geometry.get("outlines", []):
                if len(ring) < 2:
                    continue
                for a, b in zip(ring, ring[1:]):
                    pa, pb = (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
                    middle = ((pa[0]+pb[0])*.5, (pa[1]+pb[1])*.5)
                    required = (_sample_requirements([pa, middle, pb], feature, sheet_index, .75)
                                if sheet_index else [-1])
                    sheet_edge_builder.line(pa, pb, required)
                    counts["passage_sheet_edge_segments"] += 1
            sheet_record["mesh"] = sheet_mesh_builder.finish()
            sheet_record["edges"] = sheet_edge_builder.finish()
            packed_sheets.append(sheet_record)
        record.update({"mask_mesh": mask_builder.finish(),
                       "upper_mesh": upper_builder.finish(),
                       "lower_mesh": lower_builder.finish(),
                       "upper_edges": upper_edge_builder.finish(),
                       "lower_edges": lower_edge_builder.finish(),
                       "sheets": packed_sheets})
        output.append(record)
    return output, counts


def _bary_uv(source: list[tuple[float, float, float, float]], x: float, z: float) -> tuple[float, float]:
    a, b, c = source
    den = (b[1]-c[1])*(a[0]-c[0]) + (c[0]-b[0])*(a[1]-c[1])
    if abs(den) < 1e-12:
        return a[2], a[3]
    wa = ((b[1]-c[1])*(x-c[0]) + (c[0]-b[0])*(z-c[1])) / den
    wb = ((c[1]-a[1])*(x-c[0]) + (a[0]-c[0])*(z-c[1])) / den
    wc = 1.0 - wa - wb
    return (wa*a[2]+wb*b[2]+wc*c[2], wa*a[3]+wb*b[3]+wc*c[3])


def compile_art(art: dict[str, Any], rules: RegionRules, surface_index: SurfaceIndex,
                max_clearance: float, min_clearance: float) -> tuple[dict[str, Any], dict[str, int]]:
    builder = MeshBuilder()
    vertices = art.get("vertices", [])
    indices = art.get("indices", [])
    if not vertices and not indices:
        return msgpack_mesh_empty(), {"input_triangles": 0, "output_triangles": 0,
                                      "excluded_clearance_or_surface": 0,
                                      "unknown_or_mixed_samples": 0,
                                      "unknown_retained_fog_off_only": 0}
    if len(indices) % 3:
        raise ValueError("illustration index count is not divisible by three")
    parsed = []
    for vertex in vertices:
        if len(vertex) != 4 or not all(math.isfinite(float(v)) for v in vertex):
            raise ValueError("illustration vertex must be finite XZUV")
        parsed.append(tuple(map(float, vertex)))
    if any(int(i) < 0 or int(i) >= len(parsed) for i in indices):
        raise ValueError("illustration index is outside vertex array")
    excluded = unknown = output_triangles = unknown_retained = 0
    for offset in range(0, len(indices), 3):
        source = [parsed[int(indices[offset+k])] for k in range(3)]
        xy = [(v[0], v[1]) for v in source]
        source_poly = Polygon(xy)
        if source_poly.area <= 1e-10:
            excluded += 1
            continue
        centroid = (float(source_poly.centroid.x), float(source_poly.centroid.y))
        sample_xy = xy + [centroid]
        distances = [surface_index.at(x, z) for x, z in sample_xy]
        if any(distance < min_clearance - .05 or distance > max_clearance + .05
               for _, distance, _ in distances):
            excluded += 1
            continue
        if any(y is None or ambiguous for y, _, ambiguous in distances):
            # The illustration source has already been clipped by its offline
            # baker to the authored path-clearance envelope. Keep uncertain
            # floor classification available for fog-off inspection, but make
            # it explicitly unclaimed so it can never reveal through fog.
            builder.triangle(source, [-1])
            unknown += 1
            unknown_retained += 1
            output_triangles += 1
            continue
        # The 3 nearest source heights define a local support plane. Mixed or
        # singular height classification receives the same fog-off-only path.
        plane, _, ambiguous = surface_index.plane_for_triangle(sample_xy, max_clearance + .05)
        if plane is None or ambiguous:
            unknown += 1
            builder.triangle(source, [-1])
            unknown_retained += 1
            output_triangles += 1
            continue
        for geometry, required in rules.clip(source_poly, plane, margin=.25):
            for triangle in triangulate(geometry):
                uv = [_bary_uv(source, x, z) for x, z in triangle]
                builder.triangle([(x, z, u, v) for (x, z), (u, v) in zip(triangle, uv)], required)
                output_triangles += 1
    return builder.finish(), {"input_triangles": len(indices)//3,
                              "output_triangles": output_triangles,
                              "excluded_clearance_or_surface": excluded,
                              "unknown_or_mixed_samples": unknown,
                              "unknown_retained_fog_off_only": unknown_retained}


def select_art_texture(map_id: str, art: dict[str, Any], asset_dir: Path) -> tuple[str, str]:
    """Honor explicit per-map styling when present; keep the current 2-style default."""
    style_files = (PROJECT / "mapstyle.json", PROJECT / "map-style.json",
                   PROJECT / "assets" / "mapstyle.json", PROJECT / "assets" / "map-style.json",
                   asset_dir / "mapstyle.json", asset_dir / "map-style.json")
    style_value: Any = None
    style_source = "fallback-known-area-style"
    for path in style_files:
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        selected = document.get("maps", {}).get(map_id) if isinstance(document, dict) else None
        if selected is None and isinstance(document, dict):
            selected = document.get(map_id)
        if selected is not None:
            style_value = selected
            style_source = str(path)
            break
    if style_value is None:
        atlas = art.get("atlas", {})
        atlas_path = atlas.get("path", "") if isinstance(atlas, dict) else ""
        if "forest" in str(atlas_path).casefold():
            style_value, style_source = "forest", "illustrations.json atlas metadata"
        elif "urban" in str(atlas_path).casefold():
            style_value, style_source = "urban", "illustrations.json atlas metadata"
        else:
            style_value = "forest" if map_id == "m27_00_00_00" else "urban"
    if isinstance(style_value, dict):
        style_value = (style_value.get("art_style") or style_value.get("style") or
                       style_value.get("art_texture") or style_value.get("texture") or
                       style_value.get("atlas"))
    normalized = str(style_value).casefold()
    if "forest" in normalized:
        return "forest-atlas.bbra", style_source
    if "urban" in normalized:
        return "urban-atlas.bbra", style_source
    raise ValueError(f"unsupported art style for {map_id}: {style_value!r}")


def atomic_init_candidate(base_maps: Path, candidate: Path, meta_path: Path) -> dict[str, Any]:
    base_index = base_maps / "atlas2-index.json"
    if not base_index.is_file():
        raise FileNotFoundError(f"production map index missing: {base_index}")
    verified = verify_maps_tree(base_maps)
    base_sha = verified["index_sha256"]
    if candidate.exists():
        if not meta_path.is_file():
            raise RuntimeError(f"candidate exists without its safety receipt: {candidate}; refusing overwrite")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("base_index_sha256") != base_sha:
            raise RuntimeError("candidate was initialized from a different production index")
        if sha256(candidate / "atlas2-index.json") != meta.get("candidate_index_sha256"):
            raise RuntimeError("candidate index changed outside compile_navigation.py; preserving it")
        return meta
    candidate.parent.mkdir(parents=True, exist_ok=True)
    temp = candidate.with_name(candidate.name + ".initializing")
    if temp.exists():
        raise RuntimeError(f"incomplete candidate copy exists; inspect before resuming: {temp}")
    shutil.copytree(base_maps, temp)
    copied_index = temp / "atlas2-index.json"
    if sha256(copied_index) != base_sha:
        raise RuntimeError("copied production index differs from source")
    os.replace(temp, candidate)
    meta = {"schema": 1, "base_maps": str(base_maps), "base_index_sha256": base_sha,
            "checked_base_area_files": verified["checked_area_files"],
            "candidate_maps": str(candidate), "candidate_index_sha256": base_sha,
            "created_utc_epoch": time.time(), "updated_areas": []}
    atomic_write(meta_path, canonical_json(meta))
    return meta


def build_payload(map_id: str, work_dir: Path, asset_dir: Path,
                  reference_features: dict[str, Any], source_feature_hash: str) -> tuple[bytes, dict[str, Any]]:
    phase_seconds: dict[str, float] = {}
    phase_start = time.perf_counter()
    nav_path = work_dir / "navigation.json"
    triangles_path = work_dir / "navmesh-triangles.npy"
    supported_path = work_dir / "nav-supported.npy"
    art_path = asset_dir / "illustrations.json"
    for path in (nav_path, triangles_path, supported_path, art_path):
        if not path.is_file():
            raise FileNotFoundError(f"required per-map bake is missing: {path}")
    nav = json.loads(nav_path.read_text(encoding="utf-8"))
    if nav.get("region") != map_id:
        raise ValueError(f"navigation region {nav.get('region')!r} does not match {map_id}")
    all_triangles = np.load(triangles_path, allow_pickle=False)
    supported_mask = np.load(supported_path, allow_pickle=False)
    if all_triangles.ndim != 3 or all_triangles.shape[1:] != (3, 3):
        raise ValueError("navmesh-triangles.npy must be Nx3x3 XYZ")
    if supported_mask.ndim != 1 or len(supported_mask) != len(all_triangles) or supported_mask.dtype.kind != "b":
        raise ValueError("nav-supported.npy must be a same-length boolean mask")
    supported = np.asarray(all_triangles[supported_mask], dtype=np.float64)
    if not np.isfinite(supported).all() or len(supported) == 0:
        raise ValueError("supported navmesh is empty or non-finite")
    expected_count = nav.get("supported_triangle_count")
    if expected_count is not None and int(expected_count) != len(supported):
        raise ValueError("navigation supported_triangle_count does not match source mask")
    art = json.loads(art_path.read_text(encoding="utf-8"))
    if art.get("region", map_id) != map_id:
        raise ValueError("illustration region does not match map ID")
    phase_seconds["load_inputs"] = time.perf_counter() - phase_start
    print(f"[{map_id}] load_inputs: {phase_seconds['load_inputs']:.2f}s", flush=True)
    phase_start = time.perf_counter()
    surface_index = SurfaceIndex(supported)
    bounds = tuple(map(float, nav.get("bounds", [])))
    if len(bounds) != 4:
        raise ValueError("navigation bounds must contain four coordinates")
    rules = RegionRules(reference_features, bounds)
    ground, outline, fringe, surface_report = compile_surface(nav, rules, supported)
    phase_seconds["compile_surface"] = time.perf_counter() - phase_start
    print(f"[{map_id}] compile_surface: {phase_seconds['compile_surface']:.2f}s", flush=True)
    phase_start = time.perf_counter()
    chunks = []
    for offset in range(0, len(supported), 4000):
        triangles = supported[offset:offset+4000, :, :][:, :, [0, 2]]
        chunks.append(sh.union_all(sh.polygons(triangles), grid_size=.015))
    footprint = sh.make_valid(sh.union_all(chunks))
    phase_seconds["build_footprint"] = time.perf_counter() - phase_start
    print(f"[{map_id}] build_footprint: {phase_seconds['build_footprint']:.2f}s", flush=True)
    phase_start = time.perf_counter()
    sheets_path = work_dir / "passage-sheets.json"
    passage_sheets = load_passage_sheets(sheets_path, nav)
    overlap_meshes, overlap_report = compile_overlap_meshes(nav, reference_features,
                                                            surface_index, footprint,
                                                            passage_sheets)
    phase_seconds["compile_overlaps"] = time.perf_counter() - phase_start
    print(f"[{map_id}] compile_overlaps: {phase_seconds['compile_overlaps']:.2f}s", flush=True)
    phase_start = time.perf_counter()
    constraints = art.get("constraints", {})
    max_clearance = float(constraints.get("outer_fringe_limit_m", 16.0))
    min_clearance = float(constraints.get("path_clearance_m", 0.35))
    if not (0 <= min_clearance <= max_clearance <= 100):
        raise ValueError("illustration clearance metadata is invalid")
    art_mesh, art_report = compile_art(art, rules, surface_index, max_clearance, min_clearance)
    phase_seconds["compile_art"] = time.perf_counter() - phase_start
    print(f"[{map_id}] compile_art: {phase_seconds['compile_art']:.2f}s", flush=True)
    art_texture, art_style_source = select_art_texture(map_id, art, asset_dir)
    source_paths = {"navigation": nav_path, "navmesh_triangles": triangles_path,
                    "nav_supported": supported_path, "illustrations": art_path}
    if sheets_path.is_file():
        source_paths["passage_sheets"] = sheets_path
    meta = {"schema": 1, "region_id": map_id, "source_hashes": {key: sha256(path) for key, path in source_paths.items()},
            "features_sha256": source_feature_hash, "supported_triangle_count": int(len(supported)),
            "source_navmesh_triangle_count": int(len(all_triangles)),
            "reveal_region_count": len(reference_features.get("reveal_regions", [])),
            "always_visible": bool(reference_features.get("always_visible", False)),
            "art_label": art.get("label", ""), "art_texture": art_texture,
            "art_style_source": art_style_source,
            "art_constraints": constraints,
            "surface": surface_report, "overlaps": overlap_report, "art": art_report,
            "phase_seconds": phase_seconds}
    # Timing is useful in external compile reports but would make the packed
    # runtime payload nondeterministic. Keep the immutable A3Z root stable.
    payload_meta = dict(meta)
    payload_meta.pop("phase_seconds", None)
    result = {"schema": 1, "region_id": map_id, "bounds": list(bounds),
              "ground": ground, "outline": outline, "fringe": fringe,
              "art": art_mesh, "overlaps": overlap_meshes,
              "art_texture": art_texture,
              "lamps": nav.get("lamps", []), "markers": nav.get("markers", []),
              "pickups": nav.get("pickups", []), "meta": payload_meta}
    packed = a3z_pack(result)
    print(f"[{map_id}] a3z_pack: {len(packed)} bytes", flush=True)
    return packed, meta


def commit_candidate(map_id: str, payload: bytes, candidate: Path,
                     area_name: str, index: dict[str, Any],
                     meta_path: Path, meta: dict[str, Any]) -> tuple[str, str]:
    area_dir = candidate / area_name
    manifest_path = area_dir / "manifest.json"
    raw_manifest = manifest_path.read_bytes()
    indexed_row = next((row for row in index.get("areas", [])
                        if row.get("region_id") == map_id), None)
    if indexed_row is None or hashlib.sha256(raw_manifest).hexdigest() != indexed_row.get("manifest_sha256"):
        raise ValueError("candidate target area manifest does not match candidate index")
    manifest = json.loads(raw_manifest)
    if manifest.get("region_id") != map_id or manifest.get("schema") != 4:
        raise ValueError("candidate area manifest identity mismatch")
    for name, digest in manifest.get("files", {}).items():
        relative = PurePosixPath(str(name))
        if len(relative.parts) != 1 or relative.name in (".", ".."):
            raise ValueError(f"unsafe candidate area file path: {name}")
        file_path = area_dir / relative.name
        if not file_path.is_file() or sha256(file_path) != digest:
            raise ValueError(f"candidate area file hash mismatch: {area_name}/{name}")
    data_path = area_dir / "navigation.a3z"
    atomic_write(data_path, payload)
    manifest.setdefault("files", {})[data_path.name] = sha256(data_path)
    atomic_write(manifest_path, canonical_json(manifest))
    manifest_sha = sha256(manifest_path)
    index_entry = next((row for row in index["areas"] if row.get("region_id") == map_id), None)
    if index_entry is None or index_entry.get("area") != area_name:
        raise ValueError("candidate area index entry mismatch")
    index_entry["manifest_sha256"] = manifest_sha
    index_path = candidate / "atlas2-index.json"
    atomic_write(index_path, canonical_json(index))
    index_sha = sha256(index_path)
    meta["candidate_index_sha256"] = index_sha
    updated = sorted(set(meta.get("updated_areas", [])) | {map_id})
    meta["updated_areas"] = updated
    meta["last_payload"] = {"region_id": map_id, "sha256": hashlib.sha256(payload).hexdigest(),
                            "bytes": len(payload), "area_manifest_sha256": manifest_sha}
    atomic_write(meta_path, canonical_json(meta))
    return manifest_sha, index_sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-id", required=True, help="one region ID, e.g. m27_00_00_00")
    parser.add_argument("--base-maps", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--candidate-maps", type=Path, default=PROJECT / "maps-baked")
    parser.add_argument("--work-root", type=Path, default=PROJECT / "work")
    parser.add_argument("--assets-root", type=Path, default=PROJECT / "assets")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if len(args.map_id) != 12 or not args.map_id.startswith("m"):
        raise ValueError("map ID must be a 12-character Bloodborne region ID")

    # Use the same config module and authoritative features table as the other
    # per-map bakers; set MAP_ID before importing it.
    os.environ["ATLAS_MAP_ID"] = args.map_id
    sys.path.insert(0, str(PROJECT))
    import config as bake_config
    if bake_config.MAP_ID != args.map_id:
        raise ValueError("config map ID mismatch")
    index_path = args.base_maps / "atlas2-index.json"
    base_index = json.loads(index_path.read_text(encoding="utf-8"))
    if base_index.get("schema") != 1 or base_index.get("format") != "compiled-vector-v1":
        raise ValueError("unsupported production maps-baked index")
    row = next((item for item in base_index.get("areas", [])
                if item.get("region_id") == args.map_id), None)
    if row is None:
        raise ValueError(f"region is not in the production map index: {args.map_id}")
    if len(base_index.get("areas", [])) != 16:
        raise ValueError("production index must retain all 16 supported areas")

    packed, report = build_payload(args.map_id, args.work_root / args.map_id,
                                   args.assets_root / args.map_id,
                                   bake_config.FEATURES,
                                   sha256(bake_config.REF / "features.json"))
    meta_path = PROJECT / "work" / "maps-baked-candidate-receipt.json"
    meta = atomic_init_candidate(args.base_maps.resolve(), args.candidate_maps.resolve(), meta_path)
    candidate_index = json.loads((args.candidate_maps / "atlas2-index.json").read_text(encoding="utf-8"))
    candidate_row = next((item for item in candidate_index["areas"] if item.get("region_id") == args.map_id), None)
    if candidate_row is None or candidate_row.get("area") != row.get("area"):
        raise ValueError("candidate index area identity mismatch")
    area_manifest_sha, index_sha = commit_candidate(args.map_id, packed, args.candidate_maps,
                                                   row["area"], candidate_index,
                                                   meta_path, meta)
    report.update({"schema": 1, "region_id": args.map_id,
                   "candidate_maps": str(args.candidate_maps.resolve()),
                   "area": row["area"], "navigation_sha256": hashlib.sha256(packed).hexdigest(),
                   "navigation_bytes": len(packed), "area_manifest_sha256": area_manifest_sha,
                   "atlas2_index_sha256": index_sha,
                   "root_manifest_compact_maps_index_sha256": index_sha,
                   "not_installed": True})
    report_path = args.report or PROJECT / "reports" / f"{args.map_id}-navigation-compile.json"
    atomic_write(report_path, canonical_json(report))
    print(json.dumps({"region_id": args.map_id, "navigation_sha256": report["navigation_sha256"],
                      "atlas2_index_sha256": index_sha, "candidate_maps": str(args.candidate_maps),
                      "report": str(report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"compile_navigation: {exc}", file=sys.stderr)
        raise SystemExit(1)
