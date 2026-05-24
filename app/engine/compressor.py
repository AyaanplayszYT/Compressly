"""Pillow-backed image compression engine.

Design goals:
* Defensive against unsupported / corrupted inputs (Pillow raises -> we wrap).
* Atomic writes via tempfile + os.replace so an interrupted run never clobbers
  a previously-good output.
* No subprocess, no shell, no eval, no network. Pure Python + Pillow.
"""

from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional

from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

from ..models import CompressionSettings, OutputFormat, ResizeMode

# Allow Pillow to load slightly truncated images instead of raising mid-decode.
# This is a known, intentional Pillow knob; corrupted inputs still raise.
ImageFile.LOAD_TRUNCATED_IMAGES = True

# A conservative cap on decoded pixels to defend against decompression bombs.
# 200 megapixels = a 14000x14000 image, which is plenty for normal photography.
Image.MAX_IMAGE_PIXELS = 200_000_000

SUPPORTED_INPUT_EXTS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif"}
)

SUPPORTED_INPUT_MIME_HINTS: frozenset[str] = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/bmp",
        "image/gif",
        "image/tiff",
    }
)


class CompressionError(Exception):
    """Raised when an image cannot be compressed."""


@dataclass(frozen=True)
class CompressionResult:
    output_path: Path
    output_size: int
    width: int
    height: int
    duration_ms: int


def is_supported_image(path: Path) -> bool:
    """Return True if `path` looks like a supported image by extension."""
    return path.suffix.lower() in SUPPORTED_INPUT_EXTS


def iter_image_paths(roots: Iterable[Path]) -> Iterator[Path]:
    """Yield supported image paths under each root.

    * Files are yielded directly if supported.
    * Directories are walked recursively.
    * Symlinks are NOT followed (defensive against link cycles).
    """
    seen: set[Path] = set()
    for root in roots:
        try:
            root = root.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if root.is_file():
            if is_supported_image(root) and root not in seen:
                seen.add(root)
                yield root
            continue
        if root.is_dir():
            for dirpath, _dirnames, filenames in os.walk(root, followlinks=False):
                for name in filenames:
                    p = Path(dirpath) / name
                    try:
                        if p.is_symlink():
                            continue
                        if is_supported_image(p):
                            rp = p.resolve(strict=True)
                            if rp not in seen:
                                seen.add(rp)
                                yield rp
                    except OSError:
                        continue


def _resolve_output_path(source: Path, settings: CompressionSettings) -> Path:
    fmt = settings.output_format
    if fmt is OutputFormat.KEEP:
        ext = source.suffix.lstrip(".").lower() or "jpg"
        # Normalize jpeg -> jpg so file managers behave consistently
        if ext == "jpeg":
            ext = "jpg"
    else:
        ext = fmt.extension

    if settings.output_dir is not None:
        out_dir = settings.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        candidate = out_dir / f"{source.stem}.{ext}"
    else:
        candidate = source.with_name(f"{source.stem}_compressed.{ext}")

    if settings.overwrite:
        return candidate

    # Avoid clobbering: append " (n)" until unique.
    if not candidate.exists():
        return candidate
    n = 1
    while True:
        alt = candidate.with_name(f"{candidate.stem} ({n}){candidate.suffix}")
        if not alt.exists():
            return alt
        n += 1


def _resize(image: Image.Image, settings: CompressionSettings) -> Image.Image:
    if settings.resize_mode is ResizeMode.NONE:
        return image

    w, h = image.size
    if settings.resize_mode is ResizeMode.PERCENT:
        scale = max(10, min(100, settings.resize_percent)) / 100.0
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
    elif settings.resize_mode is ResizeMode.LONGEST:
        target = max(64, settings.resize_longest)
        longest = max(w, h)
        if longest <= target:
            return image
        scale = target / longest
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
    else:
        return image

    if settings.keep_aspect_ratio:
        # Aspect is already preserved by uniform scaling above.
        pass

    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _save(
    image: Image.Image,
    fmt: OutputFormat,
    quality: int,
    strip_metadata: bool,
    destination: Path,
) -> None:
    """Save `image` to `destination` atomically (temp file + replace)."""
    save_kwargs: dict[str, object] = {}
    save_format: str

    if fmt is OutputFormat.JPEG:
        save_format = "JPEG"
        if image.mode in ("RGBA", "LA", "P"):
            # JPG has no alpha — composite onto white.
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")
        save_kwargs.update({
            "quality": int(max(1, min(100, quality))),
            "optimize": True,
            "progressive": True,
        })
    elif fmt is OutputFormat.PNG:
        save_format = "PNG"
        # Map quality 1..100 to compress_level 9..0 (Pillow uses 0=fastest, 9=smallest).
        compress_level = int(round(9 - (max(1, min(100, quality)) - 1) / 99 * 9))
        save_kwargs.update({"optimize": True, "compress_level": compress_level})
    elif fmt is OutputFormat.WEBP:
        save_format = "WEBP"
        save_kwargs.update({
            "quality": int(max(1, min(100, quality))),
            "method": 6,  # max effort, slower but smallest
        })
    else:
        # KEEP — infer from extension. _resolve_output_path guarantees a known ext.
        ext = destination.suffix.lower().lstrip(".")
        if ext in ("jpg", "jpeg"):
            return _save(image, OutputFormat.JPEG, quality, strip_metadata, destination)
        if ext == "png":
            return _save(image, OutputFormat.PNG, quality, strip_metadata, destination)
        if ext == "webp":
            return _save(image, OutputFormat.WEBP, quality, strip_metadata, destination)
        raise CompressionError(f"Cannot infer output format for: {destination.name}")

    if strip_metadata:
        # Pillow only writes metadata if we hand it back explicitly. By not
        # passing exif/icc_profile we already strip it for JPEG/WebP. For PNG
        # we also drop pnginfo by simply not providing it.
        pass
    else:
        exif = image.info.get("exif")
        if exif:
            save_kwargs["exif"] = exif
        icc = image.info.get("icc_profile")
        if icc:
            save_kwargs["icc_profile"] = icc

    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".compressly_",
        suffix=destination.suffix,
        dir=str(destination.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        os.close(fd)
        image.save(str(tmp_path), format=save_format, **save_kwargs)
        os.replace(tmp_path, destination)
    except Exception:
        # Best-effort cleanup; never raise from finally.
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


def compress_image(
    source: Path,
    settings: CompressionSettings,
    *,
    cancel_check: Optional[callable] = None,  # type: ignore[type-arg]
) -> CompressionResult:
    """Compress `source` using `settings` and return the result.

    Raises CompressionError on any failure with a friendly message.
    """
    started = time.perf_counter()

    if not isinstance(source, Path):
        source = Path(source)
    try:
        source = source.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise CompressionError(f"File not found: {source}") from exc

    if not source.is_file():
        raise CompressionError(f"Not a file: {source}")
    if not is_supported_image(source):
        raise CompressionError(f"Unsupported file type: {source.suffix}")

    if cancel_check is not None and cancel_check():
        raise CompressionError("Cancelled")

    try:
        with Image.open(source) as image:
            image.load()  # force decode now so we catch errors early
            # Apply EXIF orientation so the output looks correct.
            try:
                image = ImageOps.exif_transpose(image)
            except Exception:
                pass

            if cancel_check is not None and cancel_check():
                raise CompressionError("Cancelled")

            image = _resize(image, settings)

            destination = _resolve_output_path(source, settings)
            _save(
                image,
                settings.output_format,
                settings.quality,
                settings.strip_metadata,
                destination,
            )
            width, height = image.size
    except CompressionError:
        raise
    except UnidentifiedImageError as exc:
        raise CompressionError(f"Unsupported or corrupted image: {source.name}") from exc
    except (OSError, ValueError) as exc:
        raise CompressionError(f"Failed to compress {source.name}: {exc}") from exc

    try:
        out_size = destination.stat().st_size
    except OSError:
        out_size = 0

    return CompressionResult(
        output_path=destination,
        output_size=out_size,
        width=width,
        height=height,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
