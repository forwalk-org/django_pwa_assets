"""Generator for Microsoft Tiles (msapplication-square*logo).

Windows browsers (Edge/IE) and Windows 10 Start menu tiles read the
``msapplication-*`` ``<meta>`` tags produced by this module.  Four canonical
tile sizes are generated for every run:

- 70 × 70   ``msapplication-square70x70logo``
- 150 × 150 ``msapplication-square150x150logo``
- 310 × 310 ``msapplication-square310x310logo``
- 310 × 150 ``msapplication-wide310x150logo``

Module-level constants:
    MSTILE_SPECS: Ordered tuple of :class:`MstileSpec` covering the four sizes.

All tiles are rendered as PNG with a solid background (defaults to white) and
15 % safe-zone padding around the logo.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Generator, Tuple

from PIL import Image

from .base import AssetTask, parse_color, render_canvas


@dataclass(frozen=True)
class MstileSpec:
    """Dimensions and metadata for a single Microsoft Tile.

    Attributes:
        width: Physical pixel width.
        height: Physical pixel height.
        name: The name attribute for the msapplication meta tag.
    """
    width: int
    height: int
    name: str


# Standard Microsoft Tile specifications for tiles and browser configuration
MSTILE_SPECS: Tuple[MstileSpec, ...] = (
    MstileSpec(70, 70, "msapplication-square70x70logo"),
    MstileSpec(150, 150, "msapplication-square150x150logo"),
    MstileSpec(310, 310, "msapplication-square310x310logo"),
    MstileSpec(310, 150, "msapplication-wide310x150logo"),
)


def generate_mstiles(
    img: Image.Image,
    asset_dir: str,
    **kwargs
) -> Generator[AssetTask, None, None]:
    """Generates all configured Microsoft Tiles from a source logo.

    Args:
        img: The source PIL Image (normalized to RGBA).
        asset_dir: Target directory path for saving the assets.
        **kwargs: Options like 'background' for the tile fill.

    Yields:
        AssetTask objects for each Microsoft Tile specification.
    """
    # Microsoft Tiles usually look better with a solid background
    background = kwargs.get("background") or "#ffffff"
    bg_color = parse_color(background) or (255, 255, 255, 255)

    for spec in MSTILE_SPECS:
        # Render the logo onto a canvas with a 15% safe-zone padding
        canvas = render_canvas(
            img, (spec.width, spec.height), bg_color, padding=0.15)

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")

        # Filename format: {dir}/mstile-{width}x{height}.png
        filename = f"{asset_dir}/mstile-{spec.width}x{spec.height}.png"

        yield AssetTask(
            filename=filename,
            content=buf.getvalue(),
            mimetype="image/png",
            metadata={
                "sizes": f"{spec.width}x{spec.height}",
                "name": spec.name,
                "width": spec.width,
                "height": spec.height
            }
        )
