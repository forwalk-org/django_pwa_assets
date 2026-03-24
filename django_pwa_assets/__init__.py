"""django_pwa_assets — PWA asset generation for Django.

Provides a high-performance async pipeline for generating all assets
required by a Progressive Web App:

- Standard and maskable icons (all PWA sizes).
- Favicons (.ico + .png).
- Microsoft Tiles (mstile).
- Apple splash screens (portrait + landscape, all current devices).

Quick start::

    # Async context (ASGI view, async management command)
    from django_pwa_assets import aget_or_generate_all

    assets = await aget_or_generate_all("logo.svg", background="#fff")
    assets["icons"]    # list of AssetManifestEntry
    assets["favicons"] # list of AssetManifestEntry

See ``generator.py`` for the full API reference.

Author:  Maurizio Melani
Version: 0.2.0
License: MIT
"""

__version__: str = "0.2.0"
__author__: str = "Maurizio Melani"

# Expose the complete public API at the package level so that callers do
# not need to reach into sub-modules.
from .generator import (  # noqa: E402
    AllAssets,
    AssetManifestEntry,
    AssetTask,
    aget_or_generate_all,
    aget_or_generate_favicons,
    aget_or_generate_icons,
    aget_or_generate_mstiles,
    aget_or_generate_splashes,
    aget_or_create_manifest_icon,
    get_or_generate_all,
    get_or_generate_favicons,
    get_or_generate_icons,
    get_or_generate_mstiles,
    get_or_generate_splashes,
    get_or_create_manifest_icons,
    generate_favicons,
    generate_icons,
    generate_mstiles,
    generate_splashes,
)

__all__ = [
    # Data types
    "AllAssets",
    "AssetManifestEntry",
    "AssetTask",
    # Primary entry points (Async)
    "aget_or_generate_all",
    "aget_or_generate_favicons",
    "aget_or_generate_icons",
    "aget_or_generate_mstiles",
    "aget_or_generate_splashes",
    "aget_or_create_manifest_icon",
    # Secondary entry points (sync)
    "get_or_generate_all",
    "get_or_generate_favicons",
    "get_or_generate_icons",
    "get_or_generate_mstiles",
    "get_or_generate_splashes",
    "get_or_create_manifest_icons",
    # Generator functions (for custom pipelines)
    "generate_favicons",
    "generate_icons",
    "generate_mstiles",
    "generate_splashes",
]
