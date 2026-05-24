"""Compression engine — pure functions, no Qt imports."""

from .compressor import (
    CompressionError,
    SUPPORTED_INPUT_EXTS,
    SUPPORTED_INPUT_MIME_HINTS,
    compress_image,
    is_supported_image,
    iter_image_paths,
)

__all__ = [
    "CompressionError",
    "SUPPORTED_INPUT_EXTS",
    "SUPPORTED_INPUT_MIME_HINTS",
    "compress_image",
    "is_supported_image",
    "iter_image_paths",
]
