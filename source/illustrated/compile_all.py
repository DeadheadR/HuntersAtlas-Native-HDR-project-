"""Compile ready all-area navigation payloads with bounded CPU concurrency.

Workers only read source bakes and write temporary A3Z/report files. The main
process is the sole writer of the candidate maps-baked manifests and advances
one area at a time, leaving a recoverable receipt checkpoint after each area.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any


PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))
import compile_navigation as compiler


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_map_config(map_id: str) -> Any:
    source_dir = PROJECT
    config_path = source_dir / "config.py"
    os.environ["ATLAS_MAP_ID"] = map_id
    module_name = f"atlas_bake_config_{map_id}"
    spec = importlib.util.spec_from_file_location(module_name, config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load map config: {config_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if module.MAP_ID != map_id:
        raise ValueError(f"map config identity mismatch for {map_id}")
    return module


def _compile_worker(args: tuple[str, str, str, str, str]) -> dict[str, Any]:
    map_id, work_root_raw, asset_root_raw, payload_root_raw, feature_hash = args
    work_root, asset_root = Path(work_root_raw), Path(asset_root_raw)
    payload_root = Path(payload_root_raw)
    config = _load_map_config(map_id)
    work_dir, asset_dir = work_root / map_id, asset_root / map_id
    inputs = [work_dir / "navigation.json", work_dir / "navmesh-triangles.npy",
              work_dir / "nav-supported.npy", asset_dir / "illustrations.json",
              work_dir / "passage-sheets.json"]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"{map_id}: missing immutable compiler inputs: {missing}")
    before = {str(path): sha256(path) for path in inputs}
    payload, report = compiler.build_payload(map_id, work_dir, asset_dir,
                                             config.FEATURES, feature_hash)
    after = {str(path): sha256(path) for path in inputs}
    if before != after:
        raise RuntimeError(f"{map_id}: source bake changed during compilation")
    payload_root.mkdir(parents=True, exist_ok=True)
    payload_path = payload_root / f"{map_id}.navigation.a3z"
    compiler.atomic_write(payload_path, payload)
    report_path = payload_root / f"{map_id}.compile.json"
    report.update({"schema": 1, "region_id": map_id,
                   "navigation_sha256": hashlib.sha256(payload).hexdigest(),
                   "navigation_bytes": len(payload),
                   "source_hashes_verified_before_after": True,
                   "not_installed": True})
    compiler.atomic_write(report_path, compiler.canonical_json(report))
    return {"region_id": map_id, "payload_path": str(payload_path),
            "report_path": str(report_path), "report": report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-maps", type=Path, default=compiler.DEFAULT_BASE)
    parser.add_argument("--candidate-maps", type=Path, default=PROJECT / "maps-baked")
    parser.add_argument("--work-root", type=Path, default=PROJECT / "work")
    parser.add_argument("--assets-root", type=Path, default=PROJECT / "assets")
    parser.add_argument("--report-root", type=Path, default=PROJECT / "reports")
    parser.add_argument("--max-workers", type=int, default=2,
                        help="bounded geometry CPU workers (1 or 2)")
    parser.add_argument("--map-id", action="append", help="compile selected region(s); default all indexed regions")
    args = parser.parse_args()
    if args.max_workers not in (1, 2):
        raise ValueError("--max-workers must be 1 or 2")

    verified = compiler.verify_maps_tree(args.base_maps.resolve())
    index = verified["index"]
    rows = index.get("areas", [])
    if len(rows) != 16:
        raise ValueError("all-area source index must retain 16 maps")
    wanted = set(args.map_id or [row["region_id"] for row in rows])
    row_by_id = {row["region_id"]: row for row in rows}
    unknown = wanted - row_by_id.keys()
    if unknown:
        raise ValueError(f"requested regions are absent from the source index: {sorted(unknown)}")
    ordered_ids = [row["region_id"] for row in rows if row["region_id"] in wanted]
    # Fail before starting workers if any sidecar is missing; passage-sheet
    # output must be settled for every requested map before committing a batch.
    missing_sheets = [map_id for map_id in ordered_ids
                      if not (args.work_root / map_id / "passage-sheets.json").is_file()]
    if missing_sheets:
        raise FileNotFoundError(f"passage-sheet sidecars are not ready: {missing_sheets}")

    receipt_path = PROJECT / "work" / "maps-baked-candidate-receipt.json"
    receipt = compiler.atomic_init_candidate(args.base_maps.resolve(),
                                            args.candidate_maps.resolve(), receipt_path)
    candidate_index = json.loads((args.candidate_maps / "atlas2-index.json").read_text(encoding="utf-8"))
    feature_path = _load_map_config(ordered_ids[0]).REF / "features.json"
    feature_hash = sha256(feature_path)
    payload_root = PROJECT / "work" / "compiled-payloads"
    report_rows: dict[str, dict[str, Any]] = {}
    commit_errors = []
    tasks = [(map_id, str(args.work_root.resolve()), str(args.assets_root.resolve()),
              str(payload_root.resolve()), feature_hash) for map_id in ordered_ids]
    with ProcessPoolExecutor(max_workers=args.max_workers) as pool:
        future_ids = {pool.submit(_compile_worker, task): task[0] for task in tasks}
        for future in as_completed(future_ids):
            map_id = future_ids[future]
            try:
                result = future.result()
                report = result["report"]
                row = row_by_id[map_id]
                area_manifest_sha, index_sha = compiler.commit_candidate(
                    map_id, Path(result["payload_path"]).read_bytes(),
                    args.candidate_maps.resolve(), row["area"], candidate_index,
                    receipt_path, receipt)
                report.update({"candidate_maps": str(args.candidate_maps.resolve()),
                               "area": row["area"],
                               "area_manifest_sha256": area_manifest_sha,
                               "atlas2_index_sha256": index_sha,
                               "root_manifest_compact_maps_index_sha256": index_sha})
                report_path = args.report_root / f"{map_id}-navigation-compile.json"
                compiler.atomic_write(report_path, compiler.canonical_json(report))
                report_rows[map_id] = {"payload_sha256": report["navigation_sha256"],
                                       "area_manifest_sha256": area_manifest_sha,
                                       "atlas2_index_sha256": index_sha,
                                       "report": str(report_path)}
                print(f"committed candidate {map_id}: payload {report['navigation_bytes']} B, "
                      f"index {index_sha}", flush=True)
            except Exception as exc:
                commit_errors.append({"region_id": map_id, "error": str(exc)})
                print(f"failed {map_id}: {exc}", file=sys.stderr, flush=True)
    summary = {"schema": 1, "source_index_sha256": verified["index_sha256"],
               "candidate_index_sha256": receipt.get("candidate_index_sha256"),
               "candidate_maps": str(args.candidate_maps.resolve()),
               "compiled_regions": report_rows, "errors": commit_errors,
               "complete": not commit_errors and len(report_rows) == len(ordered_ids),
               "not_installed": True}
    summary_path = args.report_root / "allmaps-compile-summary.json"
    compiler.atomic_write(summary_path, compiler.canonical_json(summary))
    print(json.dumps({"complete": summary["complete"],
                      "compiled": len(report_rows), "errors": commit_errors,
                      "candidate_index_sha256": summary["candidate_index_sha256"],
                      "summary": str(summary_path)}, indent=2), flush=True)
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"compile_all: {exc}", file=sys.stderr)
        raise SystemExit(1)
