"""Generator for standard PWA icons and apple-touch-icons.

This module produces the full icon set required by the `icons` field of a
Web App Manifest (``manifest.json``).  Three icon *purposes* are supported:

- ``any``       — general-purpose icons used by browsers and OS launchers.
- ``maskable``  — icons with safe-zone padding for adaptive icon shapes
  (Android 8+, etc.).
- ``monochrome``— single-colour icons for notification badges and similar
  OS affordances.

Module-level constants:
    ICON_SETS: Mapping of purpose name to :class:`IconSpec` with default sizes.

Typical usage (via the orchestrator):

    from django_pwa_assets.generators.icons import generate_icons
    from django_pwa_assets.generators.base import AssetTask

    tasks = list(generate_icons(pil_image, asset_dir=\"pwa/icons/abc123\"))
    # tasks is a list of AssetTask objects ready for async upload.
"""

import io
from dataclasses import dataclass
from typing import Dict, Generator, Optional, Tuple

from PIL import Image

from ..conf import setting
from .base import AssetTask, parse_color, render_canvas


@dataclass(frozen=True)
class IconSpec:
    """Configuration for a specific set of icons.

    Attributes:
        purpose: The 'purpose' attribute for the web manifest (e.g., 'any', 'maskable').
        sizes: A tuple of standard pixel dimensions (square).
    """
    purpose: str
    sizes: Tuple[int, ...]


# Industry-standard icon sets for different PWA purposes
ICON_SETS: Dict[str, IconSpec] = {
    "any": IconSpec("any", (16, 32, 72, 96, 128, 144, 152, 192, 384, 512)),
    "maskable": IconSpec("maskable", (192, 512)),
    "monochrome": IconSpec("monochrome", (192, 512)),
    "legacy": IconSpec("legacy", (16, 32, 72, 96, 120, 128, 144, 152, 180)),
}


def get_icon_sizes(purpose: str = "any", include_legacy: bool = False) -> Tuple[int, ...]:
    """Retrieves the list of target pixel sizes for a specific icon purpose.

    Args:
        purpose: The web manifest purpose ('any', 'maskable', 'monochrome').
        include_legacy: Whether to include legacy iOS/Android sizes in the 'any' set.

    Returns:
        A sorted tuple of unique integer sizes.

    Raises:
        ValueError: If the requested purpose is not defined in ICON_SETS.
    """
    spec = ICON_SETS.get(purpose)
    if not spec:
        raise ValueError(f"Unknown icon purpose: {purpose}")

    # Allow setting-based overrides for each purpose
    setting_key = f"ICON_SIZES_{purpose.upper()}"
    sizes = list(setting(setting_key) or spec.sizes)

    # Automatically extend 'any' with legacy sizes if requested
    if purpose == "any" and include_legacy:
        sizes.extend(ICON_SETS["legacy"].sizes)

    return tuple(sorted(set(sizes)))


def generate_icons(
    img: Image.Image,
    asset_dir: str,
    output_format: str = "png",
    jpeg_quality: int = 80,
    **kwargs
) -> Generator[AssetTask, None, None]:
    """Generates a suite of square icons from a source logo.

    Args:
        img: The source PIL Image (normalized to RGBA by the orchestrator).
        asset_dir: The target directory path for saving assets.
        output_format: 'png' or 'jpg' (defaults to 'png').
        jpeg_quality: Quality factor for JPEG output (1-100).
        **kwargs: Additional options like 'background', 'opaque', and 'purposes'.

    Yields:
        AssetTask objects for each generated icon size and purpose.
    """
    # Resolve background settings
    background = setting("BACKGROUND_COLOR", override=kwargs.get("background"))
    opaque = setting("OPAQUE", override=kwargs.get("opaque"))
    include_legacy = setting("INCLUDE_LEGACY_SIZES", override=kwargs.get("include_legacy"))

    # Default to all major purposes if none are specified
    purposes = kwargs.get("purposes")
    if not purposes:
        p = kwargs.get("purpose")
        purposes = (p,) if p else setting("PURPOSES")

    # Determine output format and file extension
    fmt = output_format.upper()
    if fmt == "JPG":
        fmt = "JPEG"
    ext = "jpg" if fmt == "JPEG" else "png"
    mimetype = f"image/{fmt.lower()}"

    # Default to transparent background unless specified otherwise
    if not background and not opaque:
        bg_color = (0, 0, 0, 0)
    else:
        bg_color = parse_color(background) or (255, 255, 255, 255)

    if hasattr(img, 'source_svg'):
        # Add svg icon if source is from svg file
        yield AssetTask(
            filename=f"{asset_dir}/icon.svg",
            content=img.source_svg,
            mimetype="image/svg+xml",
            metadata={
                "sizes": "any",
                "purpose": "any",
                "type": "image/svg+xml"
            }
        )

    for purpose in purposes:
        try:
            sizes = get_icon_sizes(purpose, include_legacy=include_legacy)
        except ValueError:
            continue

        # Determine padding
        if purpose == "maskable":
            safe_area = setting("MASKABLE_SAFE_AREA", override=kwargs.get("maskable_safe_area"))
            pad = (1.0 - safe_area) / 2.0
        else:
            pad = setting("PADDING_RATIO", override=kwargs.get("padding_ratio"))

        for size in sizes:
            # Render the logo onto a square canvas of the target size
            canvas = render_canvas(img, (size, size), bg_color=bg_color, padding=pad)

            buf = io.BytesIO()
            save_kwargs = {"format": fmt}
            if fmt == "JPEG":
                save_kwargs["quality"] = jpeg_quality
                # JPEG requires RGB mode (no alpha)
                save_img = canvas.convert("RGB")
            else:
                save_img = canvas

            save_img.save(buf, **save_kwargs)

            # Generate a semantic filename: {dir}/{purpose}-{size}x{size}.{ext}
            filename = f"{asset_dir}/{purpose}-{size}x{size}.{ext}"

            yield AssetTask(
                filename=filename,
                content=buf.getvalue(),
                mimetype=mimetype,
                metadata={
                    "sizes": f"{size}x{size}",
                    "purpose": purpose,
                    # Special Case: 180x180 is the standard apple-touch-icon
                    "rel": "apple-touch-icon" if size == 180 else "icon",
                }
            )
