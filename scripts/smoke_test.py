"""End-to-end smoke test — create a test image, run all formats/presets,
verify each output file exists and is smaller than the source for lossy formats.

Run from the project root: python smoke_test.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PIL import Image

# Ensure the local package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import compress_image, is_supported_image
from app.models import CompressionSettings, OutputFormat, ResizeMode
from app.presets import PRESETS


def make_test_image(path: Path, size: tuple[int, int] = (1600, 1200)) -> None:
    """Create a moderately complex test image."""
    img = Image.new("RGB", size, (12, 12, 24))
    pixels = img.load()
    for y in range(size[1]):
        for x in range(size[0]):
            r = (x * 255) // size[0]
            g = (y * 255) // size[1]
            b = ((x + y) * 255) // (size[0] + size[1])
            pixels[x, y] = (r, g, b)
    img.save(path, format="JPEG", quality=95)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="compressly_smoke_") as td:
        td_path = Path(td)
        source = td_path / "test.jpg"
        make_test_image(source)
        original = source.stat().st_size
        print(f"[smoke] source size: {original} bytes  ({source})")
        assert is_supported_image(source)

        # Test each format
        for fmt in (OutputFormat.WEBP, OutputFormat.JPEG, OutputFormat.PNG):
            out_dir = td_path / f"out_{fmt.value}"
            settings = CompressionSettings(
                output_format=fmt,
                quality=80,
                resize_mode=ResizeMode.NONE,
                output_dir=out_dir,
            )
            result = compress_image(source, settings)
            assert result.output_path.exists(), f"missing output: {result.output_path}"
            print(
                f"[smoke] {fmt.display:12s} → {result.output_size:>9} bytes "
                f"({result.duration_ms} ms)  {result.output_path.name}"
            )
            if fmt in (OutputFormat.WEBP, OutputFormat.JPEG):
                assert result.output_size < original, f"{fmt} did not reduce size"

        # Test resize modes
        for mode, kwargs in (
            (ResizeMode.PERCENT, {"resize_percent": 50}),
            (ResizeMode.LONGEST, {"resize_longest": 800}),
        ):
            out_dir = td_path / f"out_resize_{mode.value}"
            settings = CompressionSettings(
                output_format=OutputFormat.WEBP,
                quality=80,
                resize_mode=mode,
                output_dir=out_dir,
                **kwargs,
            )
            result = compress_image(source, settings)
            assert result.output_path.exists()
            assert result.output_size < original
            print(
                f"[smoke] resize {mode.value:8s} → {result.output_size:>9} bytes  "
                f"({result.width}x{result.height})"
            )

        # Test every preset
        for preset in PRESETS:
            out_dir = td_path / f"preset_{preset.key}"
            settings = preset.apply(CompressionSettings(output_dir=out_dir))
            result = compress_image(source, settings)
            assert result.output_path.exists()
            print(
                f"[smoke] preset {preset.key:10s} → {result.output_size:>9} bytes "
                f"({result.width}x{result.height})"
            )

    print("[smoke] all checks passed ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
