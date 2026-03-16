"""PWA asset generation orchestrator.

This module exposes the complete public API of ``django_pwa_assets``.  It acts
as a thin façade over the :mod:`generators` sub-package, providing:

- **Async entry points** (``aget_or_generate_*``) — for ASGI views and async
  management commands.
- **Sync entry points** (``get_or_generate_*``) — synchronous wrappers that
  delegate to their async counterparts via :func:`asgiref.sync.async_to_sync`.
- **Type aliases** — :data:`AllAssets` for the combined result type.

All generation arguments (``background``, ``purposes``, ``portrait_only``, …)
are passed straight through to the underlying generators and are therefore
documented in detail in the respective generator modules.

Example::

    # Async context
    from django_pwa_assets.generator import aget_or_generate_all

    assets = await aget_or_generate_all("logo.svg", background="#ffffff")
    # assets["icons"]    → list[AssetManifestEntry]
    # assets["favicons"] → list[AssetManifestEntry]

    # Sync context
    from django_pwa_assets.generator import get_or_generate_all

    assets = get_or_generate_all("logo.svg", background="#ffffff")
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from PIL.Image import Image
from asgiref.sync import async_to_sync

from .conf import setting
from .generators import (
    AssetManifestEntry,
    AssetTask,
    get_or_generate_assets_async,
    generate_favicons,
    generate_icons,
    generate_mstiles,
    generate_splashes,
    parse_color,
)

# ---------------------------------------------------------------------------
# Public Entry Points
# ---------------------------------------------------------------------------
# Type aliases for public API.
AllAssets = Dict[str, List[AssetManifestEntry]]


async def aget_or_generate_icons(img: Image, **kwargs) -> List[AssetManifestEntry]:
    """Generates or returns cached PWA icons for all configured purposes.

    Resolves the ``purposes`` list from the ``PURPOSES`` setting when not
    explicitly provided, then delegates to the async orchestrator.

    Args:
        img: Source image — a file-system path (str/Path), raw bytes, a
            file-like object, or a PIL Image.
        **kwargs: Optional overrides forwarded to :func:`generators.generate_icons`.
            Common options:

            - ``background`` (str) — fill colour for icons with a solid canvas.
            - ``purposes`` (tuple[str]) — e.g. ``("any", "maskable")``.
            - ``opaque`` (bool) — force a solid white background.
            - ``force`` (bool) — skip cache and regenerate.

    Returns:
        A list of :class:`generators.AssetManifestEntry` dicts, one per icon
        file produced.
    """
    # Pull default purposes from settings if not in kwargs
    if "purposes" not in kwargs:
        kwargs["purposes"] = setting("PURPOSES") or (
            "any", "maskable", "monochrome")

    return await get_or_generate_assets_async(img, generate_icons, **kwargs)


async def aget_or_generate_favicons(img: Image, **kwargs) -> List[AssetManifestEntry]:
    """Generate favicons and return the list of manifest entries."""
    return await get_or_generate_assets_async(img, generate_favicons, **kwargs)


async def aget_or_generate_mstiles(img: Image, **kwargs) -> List[AssetManifestEntry]:
    """Generates or returns cached Microsoft Tiles.

    Args:
        img: Source image (any supported type).
        **kwargs: Optional overrides forwarded to
            :func:`generators.generate_mstiles` (e.g. ``background``).

    Returns:
        A list of :class:`generators.AssetManifestEntry` dicts.
    """
    return await get_or_generate_assets_async(img, generate_mstiles, **kwargs)


async def aget_or_generate_splashes(img: Image, **kwargs) -> List[AssetManifestEntry]:
    """Generates or returns cached iOS/iPadOS splash screens.

    Resolves ``portrait_only`` and ``min_ios`` from settings when they are not
    explicitly provided in ``kwargs``.

    Args:
        img: Source image (any supported type).
        **kwargs: Optional overrides forwarded to
            :func:`generators.generate_splashes`.  Common options:

            - ``background`` (str)      — light-mode fill colour.
            - ``dark_background`` (str) — enables the dark-mode splash set.
            - ``portrait_only`` (bool)  — skip landscape variants.
            - ``min_ios`` (str)         — minimum iOS version filter (e.g. ``"iOS 14"``).
            - ``force`` (bool)          — skip cache and regenerate.

    Returns:
        A list of :class:`generators.AssetManifestEntry` dicts.
    """
    # Pull defaults from settings if not in kwargs
    if "portrait_only" not in kwargs:
        kwargs["portrait_only"] = setting("SPLASH_PORTRAIT_ONLY")
    if "min_ios" not in kwargs:
        kwargs["min_ios"] = setting("SPLASH_MIN_IOS")

    return await get_or_generate_assets_async(img, generate_splashes, **kwargs)


async def aget_or_generate_all(img: Image, **kwargs) -> AllAssets:
    """
    Generate all assets categories in a single call.
    """
    with_favicons = kwargs.get("with_favicons", True)
    with_splashes = kwargs.get("with_splashes", True)
    with_mstiles = kwargs.get("with_mstiles", False)

    results: AllAssets = {}
    results["icons"] = await aget_or_generate_icons(img, **kwargs)

    if with_favicons:
        results["favicons"] = await aget_or_generate_favicons(img, **kwargs)

    if with_splashes:
        results["splashes"] = await aget_or_generate_splashes(img, **kwargs)

    if with_mstiles:
        results["mstiles"] = await aget_or_generate_mstiles(img, **kwargs)

    return results


def get_or_generate_icons(img: Image, **kwargs) -> List[AssetManifestEntry]:
    """Synchronous wrapper for aget_or_generate_icons."""
    return async_to_sync(aget_or_generate_icons)(img, **kwargs)


def get_or_generate_favicons(img: Image, **kwargs) -> List[AssetManifestEntry]:
    """Synchronous wrapper for aget_or_generate_favicons."""
    return async_to_sync(aget_or_generate_favicons)(img, **kwargs)


def get_or_generate_mstiles(img: Image, **kwargs) -> List[AssetManifestEntry]:
    """Synchronous wrapper for aget_or_generate_mstiles."""
    return async_to_sync(aget_or_generate_mstiles)(img, **kwargs)


def get_or_generate_splashes(img: Image, **kwargs) -> List[AssetManifestEntry]:
    """Synchronous wrapper for aget_or_generate_splashes."""
    return async_to_sync(aget_or_generate_splashes)(img, **kwargs)


def get_or_generate_all(img: Image, **kwargs) -> AllAssets:
    """Synchronous wrapper for aget_or_generate_all."""
    return async_to_sync(aget_or_generate_all)(img, **kwargs)
