"""Generators package for PWA asset types.

This package bundles all asset-specific generators and re-exports the
shared orchestration machinery from :mod:`.base`.

Available generators:
    - :func:`.generate_icons`    — standard, maskable, and monochrome PWA icons.
    - :func:`.generate_favicons` — browser favicons (.ico + PNG variants).
    - :func:`.generate_mstiles`  — Microsoft Windows Tiles.
    - :func:`.generate_splashes` — iOS/iPadOS splash screens.

Orchestration helpers (re-exported from :mod:`.base`):
    - :class:`.AssetManifestEntry` — typed dict for a single manifest entry.
    - :class:`.AssetTask`          — rendered image ready for storage upload.
    - :func:`.get_or_generate_assets_async` — primary async entry point.
    - :func:`.parse_color`         — RGBA color parser shared by all generators.

Example::

    from django_pwa_assets.generators import generate_icons, AssetManifestEntry
"""

from .base import (
    AssetManifestEntry,
    AssetTask,
    get_or_generate_assets_async,
    parse_color,
)
from .favicons import generate_favicons
from .icons import generate_icons
from .mstiles import generate_mstiles
from .splashes import generate_splashes, splash_filename

__all__ = [
    "AssetManifestEntry",
    "AssetTask",
    "get_or_generate_assets_async",
    "parse_color",
    "generate_favicons",
    "generate_icons",
    "generate_mstiles",
    "generate_splashes",
    "splash_filename",
]
