"""Native background removal using Pillow only — no external models needed.

Algorithm:
  1. Convert to RGBA
  2. Detect the dominant background colour (corner sampling)
  3. Build an alpha mask using colour distance from the background
  4. Apply Gaussian blur to smooth the mask edges
  5. Optionally use edge detection to refine the mask boundary
  6. Return the image with the background made transparent

This works well for:
  - Product photos on solid/near-solid backgrounds
  - Images with clear foreground/background contrast
  - Studio shots, screenshots, logos

For complex natural scenes, rembg (ONNX) gives better results.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageFilter, ImageOps


def _colour_distance(c1: tuple, c2: tuple) -> float:
    """Euclidean distance in RGB space."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1[:3], c2[:3])))


def _sample_background(img: Image.Image, sample_size: int = 5) -> tuple:
    """Sample the background colour from the image corners and edges."""
    w, h = img.size
    rgb = img.convert("RGB")
    pixels = rgb.load()

    samples = []
    # Corners
    for x, y in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        for dx in range(sample_size):
            for dy in range(sample_size):
                px = min(x + dx if x == 0 else x - dx, w - 1)
                py = min(y + dy if y == 0 else y - dy, h - 1)
                samples.append(pixels[px, py])

    # Top and bottom edges (middle strip)
    mid_x = w // 2
    for y in range(min(sample_size, h)):
        samples.append(pixels[mid_x, y])
        samples.append(pixels[mid_x, h - 1 - y])

    # Left and right edges (middle strip)
    mid_y = h // 2
    for x in range(min(sample_size, w)):
        samples.append(pixels[x, mid_y])
        samples.append(pixels[w - 1 - x, mid_y])

    # Return the median colour
    r = sorted(s[0] for s in samples)[len(samples) // 2]
    g = sorted(s[1] for s in samples)[len(samples) // 2]
    b = sorted(s[2] for s in samples)[len(samples) // 2]
    return (r, g, b)


def remove_background(
    source: Path,
    *,
    threshold: float = 30.0,
    edge_blur: float = 2.0,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> Image.Image:
    """Remove the background from `source` and return an RGBA image.

    Parameters
    ----------
    source:
        Path to the input image.
    threshold:
        Colour distance threshold (0–255). Higher = more aggressive removal.
        Default 30 works well for clean studio backgrounds.
    edge_blur:
        Gaussian blur radius applied to the alpha mask for smooth edges.
    cancel_check:
        Optional callable; if it returns True the operation is cancelled.

    Returns
    -------
    PIL.Image.Image in RGBA mode with background pixels made transparent.
    """
    with Image.open(source) as img:
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGBA")

    if cancel_check and cancel_check():
        raise RuntimeError("Cancelled")

    w, h = img.size
    bg_colour = _sample_background(img)

    # Build alpha mask: pixels close to bg_colour → transparent (0)
    # pixels far from bg_colour → opaque (255)
    pixels = img.load()
    mask = Image.new("L", (w, h), 0)
    mask_pixels = mask.load()

    for y in range(h):
        if cancel_check and cancel_check():
            raise RuntimeError("Cancelled")
        for x in range(w):
            r, g, b, a = pixels[x, y]
            dist = _colour_distance((r, g, b), bg_colour)
            # Smooth transition around the threshold
            if dist >= threshold:
                alpha = 255
            elif dist <= threshold * 0.4:
                alpha = 0
            else:
                # Linear ramp in the transition zone
                t = (dist - threshold * 0.4) / (threshold * 0.6)
                alpha = int(t * 255)
            mask_pixels[x, y] = alpha

    # Smooth the mask edges
    if edge_blur > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=edge_blur))

    # Apply the mask to the alpha channel
    r_ch, g_ch, b_ch, _ = img.split()
    result = Image.merge("RGBA", (r_ch, g_ch, b_ch, mask))
    return result
