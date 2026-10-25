"""Convert the reviewed RGBA PNG atlases to the native BBRA texture format."""
from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PIL import Image


DEFAULT_INPUT = Path(__file__).resolve().parent / "assets"


def convert(source: Path, destination: Path) -> None:
    with Image.open(source) as image:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        if width <= 0 or height <= 0 or width > 4096 or height > 4096:
            raise ValueError(f"unsupported atlas dimensions: {width}x{height}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"BBRA" + struct.pack("<II", width, height) + rgba.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT,
                        help="directory containing forest-atlas.png and urban-atlas.png")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="output directory for native forest-atlas.bbra and urban-atlas.bbra")
    args = parser.parse_args()
    for name in ("forest-atlas", "urban-atlas"):
        source = args.input_dir / f"{name}.png"
        if not source.is_file():
            raise FileNotFoundError(source)
        convert(source, args.output_dir / f"{name}.bbra")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
