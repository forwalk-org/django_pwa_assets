"""Generator for iOS/iPadOS splash screens (apple-touch-startup-image).

iOS uses ``<link rel="apple-touch-startup-image">`` tags to display a
full-screen splash while the PWA is loading.  Each **device × orientation**
pair requires its own image matched by a precise CSS media query.

This module covers 12 device variants (portrait + landscape each) from
iPhone 11 / iOS 12 up to iPhone 16 Pro Max / iOS 18, plus iPad Pro 13\".

Dark mode support:
    When ``dark_background`` is configured a second set of images is generated
    with ``(prefers-color-scheme: dark)`` appended to each media query,
    enabling iOS 13+ to switch automatically between light and dark splash
    screens.

Module-level constants:
    SPLASH_SCREENS: Complete tuple of :class:`SplashSpec` objects, built from
        ``_IOS_RAW_DEVICES`` by :func:`_build_splashes`.
    _IOS_RAW_DEVICES: Raw device table mapping device name to canvas size, CSS
        logical size, device-pixel-ratio, and minimum iOS version.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, Generator, Optional, Tuple

from PIL import Image

from ..conf import setting
from .base import AssetTask, parse_color, render_canvas


@dataclass(frozen=True)
class SplashSpec:
    """Dimensions and metadata for an iOS/iPadOS splash screen.

    Attributes:
        width: Physical pixel width.
        height: Physical pixel height.
        device: Human-readable device name.
        orientation: 'portrait' or 'landscape'.
        media_query: The specific CSS media query required by iOS for this splash.
        since_ios: The iOS version that introduced this spec.
    """
    width: int
    height: int
    device: str
    orientation: str
    media_query: str
    since_ios: str


# Raw device metadata for iOS splash screen generation.
# Format: {name: (canvas_w, canvas_h, logical_w, logical_h, dpr, ios_version)}
_IOS_RAW_DEVICES: Dict[str, Tuple[int, int, int, int, int, str]] = {
    "iPhone 16 Pro Max":            (1320, 2868, 440, 956, 3, "18"),
    "iPhone 16 Pro":                (1206, 2622, 402, 874, 3, "18"),
    "iPhone 16 Plus/15 Pro Max":    (1290, 2796, 430, 932, 3, "16"),
    "iPhone 16/15 Pro/14 Pro":      (1179, 2556, 393, 852, 3, "16"),
    "iPhone 14 Plus/13 Pro Max":    (1284, 2778, 428, 926, 3, "14"),
    "iPhone 14/13 Pro/12":          (1170, 2532, 390, 844, 3, "14"),
    "iPhone 11 Pro Max/XS Max":     (1242, 2688, 414, 896, 3, "12"),
    "iPhone 11/XR":                 (828,  1792, 414, 896, 2, "12"),
    "iPhone 11 Pro/X/XS":           (1125, 2436, 375, 812, 3, "11"),
    'iPad Pro 13" M4':              (2064, 2752, 1032, 1376, 2, "17"),
    'iPad Pro 12.9"':               (2048, 2732, 1024, 1366, 2, "9"),
    'iPad Mini 8.3" 6th':           (1488, 2266, 744,  1133, 2, "15"),
}

_SPLASH_MEDIA_QUERY_TEMPLATE: str = (
    "(device-width: {dw}px) and (device-height: {dh}px)"
    " and (-webkit-device-pixel-ratio: {dpr})"
)


def _build_splashes() -> Tuple[SplashSpec, ...]:
    """Expands the raw device table into a full list of portrait and landscape specs."""
    specs = []
    for device_name, (w, h, dw, dh, dpr, ios) in _IOS_RAW_DEVICES.items():
        base_mq = _SPLASH_MEDIA_QUERY_TEMPLATE.format(dw=dw, dh=dh, dpr=dpr)

        # Portrait variant
        specs.append(SplashSpec(
            width=w, height=h,
            device=device_name,
            orientation="portrait",
            media_query=f"{base_mq} and (orientation: portrait)",
            since_ios=f"iOS {ios}",
        ))

        # Landscape variant
        specs.append(SplashSpec(
            width=h, height=w,
            device=device_name,
            orientation="landscape",
            media_query=f"{base_mq} and (orientation: landscape)",
            since_ios=f"iOS {ios}",
        ))
    return tuple(specs)


SPLASH_SCREENS: Tuple[SplashSpec, ...] = _build_splashes()


def get_splash_screens(
    portrait_only: bool = False,
    landscape_only: bool = False,
    min_ios: Optional[str] = None,
) -> Tuple[SplashSpec, ...]:
    """Filters the master list of splash screen specifications.

    Args:
        portrait_only: If True, returns only portrait orientation specs.
        landscape_only: If True, returns only landscape orientation specs.
        min_ios: Optional minimum iOS version filter (e.g., '14' or 'iOS 14').

    Returns:
        A filtered tuple of SplashSpec objects.
    """
    result = list(SPLASH_SCREENS)
    if portrait_only:
        result = [s for s in result if s.orientation == "portrait"]
    elif landscape_only:
        result = [s for s in result if s.orientation == "landscape"]

    if min_ios:
        try:
            min_ver = float(min_ios.replace("iOS", "").strip())
            result = [s for s in result if float(
                s.since_ios.replace("iOS", "").strip()) >= min_ver]
        except (ValueError, TypeError):
            # Fallback to no filter if version string is malformed
            pass

    return tuple(result)


def splash_filename(spec: SplashSpec, dark: bool = False) -> str:
    """Returns the standardized filename for a splash screen.

    Args:
        spec: The SplashSpec object.
        dark: Whether it's the dark mode variant.

    Returns:
        A string filename like 'splash-1179x2556-portrait-dark.png'.
    """
    suffix = "-dark" if dark else ""
    return f"splash-{spec.width}x{spec.height}-{spec.orientation}{suffix}.png"


def generate_splashes(
    img: Image.Image,
    asset_dir: str,
    output_format: str = "png",
    jpeg_quality: int = 80,
    **kwargs
) -> Generator[AssetTask, None, None]:
    """Generates a comprehensive set of iOS splash screens.

    Args:
        img: The source PIL Image (normalized to RGBA).
        asset_dir: Target directory path for saving the generated files.
        output_format: 'png' or 'jpg' (defaults to 'png').
        jpeg_quality: Quality for JPEG output (1-100).
        **kwargs: Options like 'background', 'dark_background', and filters.

    Yields:
        AssetTask objects for both standard and (optionally) dark splash screens.
    """
    # Resolve background colors
    background = setting("BACKGROUND_COLOR", override=kwargs.get("background"))
    dark_background = setting("SPLASH_DARK_BACKGROUND",
                              override=kwargs.get("dark_background"))
    portrait_only = kwargs.get("portrait_only", False)
    min_ios = kwargs.get("min_ios")

    bg_color = parse_color(background) or (255, 255, 255, 255)
    dark_bg_color = parse_color(dark_background)

    # Output format configuration
    fmt = output_format.upper()
    if fmt == "JPG":
        fmt = "JPEG"
    ext = "jpg" if fmt == "JPEG" else "png"
    mimetype = f"image/{fmt.lower()}"

    specs = get_splash_screens(portrait_only=portrait_only, min_ios=min_ios)

    for spec in specs:
        # 1. Standard (Light) Splash Screen
        canvas = render_canvas(
            img, (spec.width, spec.height), bg_color, padding=0.25)
        buf = io.BytesIO()
        save_kwargs = {"format": fmt}
        if fmt == "JPEG":
            save_kwargs["quality"] = jpeg_quality
            save_img = canvas.convert("RGB")
        else:
            save_img = canvas

        save_img.save(buf, **save_kwargs)
        filename = f"{asset_dir}/splash-{spec.width}x{spec.height}-{spec.orientation}.{ext}"

        yield AssetTask(
            filename=filename,
            content=buf.getvalue(),
            mimetype=mimetype,
            metadata={
                "sizes": f"{spec.width}x{spec.height}",
                "media": spec.media_query,
                "rel": "apple-touch-startup-image",
                "width": spec.width,
                "height": spec.height,
            }
        )

        # 2. Dark Mode Splash Screen (if dark_background is configured)
        if dark_bg_color:
            dark_canvas = render_canvas(
                img, (spec.width, spec.height), dark_bg_color, padding=0.25)
            buf = io.BytesIO()
            if fmt == "JPEG":
                save_img = dark_canvas.convert("RGB")
            else:
                save_img = dark_canvas
            save_img.save(buf, **save_kwargs)
            filename = f"{asset_dir}/splash-{spec.width}x{spec.height}-{spec.orientation}-dark.{ext}"

            # Append the prefers-color-scheme media query for iOS dark mode support
            dark_mq = f"{spec.media_query} and (prefers-color-scheme: dark)"

            yield AssetTask(
                filename=filename,
                content=buf.getvalue(),
                mimetype=mimetype,
                metadata={
                    "sizes": f"{spec.width}x{spec.height}",
                    "media": dark_mq,
                    "rel": "apple-touch-startup-image",
                    "dark": True,
                    "width": spec.width,
                    "height": spec.height
                }
            )
