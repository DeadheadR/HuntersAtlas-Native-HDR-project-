"""Shared paths and reference metadata for the illustrated map pipeline.

Set ATLAS_REFERENCE_DIR to the extracted reference data root. It may contain
features.json, atlas.json, maps/<region>.json directly, or those metadata and
region files together inside a maps/ subdirectory.
"""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = Path(__file__).resolve().parent
MAP_ID = os.environ.get("ATLAS_MAP_ID", "m27_00_00_00")
_reference = os.environ.get("ATLAS_REFERENCE_DIR")
if not _reference:
    raise RuntimeError("Set ATLAS_REFERENCE_DIR to the extracted Atlas reference directory")
REFERENCE = Path(_reference).expanduser().resolve()
MAPS = REFERENCE / "maps" if (REFERENCE / "maps").is_dir() else REFERENCE
REF = MAPS if (MAPS / "features.json").is_file() else REFERENCE
SRC = Path(os.environ.get("ATLAS_GENERATOR_SOURCE", str(ROOT / "generator" / "src"))).expanduser().resolve()
_game_dir = os.environ.get("ATLAS_GAME_DIR")
GAME_DIR = Path(_game_dir).expanduser().resolve() if _game_dir else None
WORK = Path(os.environ.get("ATLAS_WORK_DIR", str(PIPELINE / "work"))).resolve() / MAP_ID
ASSET = Path(os.environ.get("ATLAS_ASSET_DIR", str(PIPELINE / "assets"))).resolve() / MAP_ID
WORK.mkdir(parents=True, exist_ok=True)
ASSET.mkdir(parents=True, exist_ok=True)
MAP_PATH = MAPS / f"{MAP_ID}.json"
for required in (MAP_PATH, REF / "features.json", REF / "atlas.json"):
    if not required.is_file():
        raise FileNotFoundError(f"Missing reference input: {required}")
MAP = json.loads(MAP_PATH.read_text(encoding="utf-8"))
FEATURES = json.loads((REF / "features.json").read_text(encoding="utf-8"))["areas"][MAP_ID]
ATLAS_META = json.loads((REF / "atlas.json").read_text(encoding="utf-8"))
