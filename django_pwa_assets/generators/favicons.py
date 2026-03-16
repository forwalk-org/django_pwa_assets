"""Generator for browser favicons (.ico and .png).

Produces the traditional browser-tab icon assets:

- ``favicon.ico`` — multi-frame ICO container (16 × 16 and 32 × 32 frames),
  recognised by all browsers including legacy IE.
- ``favicon-16x16.png`` / ``favicon-32x32.png`` — modern PNG variants used
  by contemporary browsers and PWA manifests.

Module-level constants:
    FAVICON_SIZES: Tuple of PNG sizes generated alongside the ICO file.

The output files are always rendered with a fully transparent background so
that the logo sits naturally on any browser chrome colour.
"""

from __future__ import annotations

import io
from typing import Generator, Tuple

from PIL import Image

from .base import AssetTask, render_canvas


FAVICON_SIZES: Tuple[int, ...] = (16, 32)


def generate_favicons(
    img: Image.Image,
    asset_dir: str,
    **kwargs
) -> Generator[AssetTask, None, None]:
    """Generates standard browser favicons including a multi-frame ICO file.

    Args:
        img: The source PIL Image (normalized to RGBA).
        asset_dir: Target directory path for saving assets.
        **kwargs: Optional keyword arguments (currently unused for favicons).

    Yields:
        AssetTask objects for 'favicon.ico' and individual PNG favicons.
    """
    # 1. Multi-frame ICO (typically contains 16x16 and 32x32 frames)
    ico_buf = io.BytesIO()
    # ICO format can store multiple sizes; we use 32x32 as the primary resizing target
    ico_logo = img.resize((32, 32), Image.Resampling.LANCZOS)
    ico_logo.save(ico_buf, format="ICO", sizes=[(16, 16), (32, 32)])

    yield AssetTask(
        filename=f"{asset_dir}/favicon.ico",
        content=ico_buf.getvalue(),
        mimetype="image/x-icon",
        metadata={"rel": "shortcut icon"}
    )

    # 2. Individual PNG Favicons (for modern browsers and manifests)
    for s in FAVICON_SIZES:
        # Favicons are almost always rendered with a transparent background
        canvas = render_canvas(img, (s, s), bg_color=(0, 0, 0, 0))

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")

        yield AssetTask(
            filename=f"{asset_dir}/favicon-{s}x{s}.png",
            content=buf.getvalue(),
            mimetype="image/png",
            metadata={"sizes": f"{s}x{s}", "rel": "icon"}
        )
