"""Settings resolver for django_pwa_assets.

Resolves configuration values using a three-level priority chain::

    runtime override  >  PWA_ASSETS Django setting  >  DEFAULTS

Usage pattern — call :func:`setting` anywhere a configuration value is
needed.  Pass an *override* keyword argument when the caller has an
explicit value that should take precedence over project settings (e.g.
a value supplied directly to a management command or template tag)::

    # Read from project settings (or defaults if not set)
    bg = setting("BACKGROUND_COLOR")

    # Runtime override: uses "#FF0000" instead of whatever is in settings
    bg = setting("BACKGROUND_COLOR", override="#FF0000")

Sentinel logic:
    ``None`` and the empty string are treated as *"not provided"* at every
    level so that callers can pass optional parameters without needing to
    check for falsy values themselves.

Example::

    from django_pwa_assets.conf import setting

    output_path = setting("OUTPUT_PATH")          # "pwa/icons"  (default)
    quality = setting("JPEG_QUALITY", override=95) # 95           (override)
"""

from __future__ import annotations

from typing import Any

from django.conf import settings as django_settings

# Sentinel object: distinguishes "caller passed nothing" from "caller passed None".
_UNSET: object = object()

#: Default values for every recognised setting key.
#: Override any of these in your Django ``settings.py`` under ``PWA_ASSETS``.
DEFAULTS: dict[str, Any] = {
    # Source image defaults.
    "DEFAULT_IMAGE": None,

    # SVG pre-processing.
    "CLEAN_IMAGE_SVG": False,
    "RAISE_ON_CLEAN_IMAGE_SVG_ERROR": False,

    # Storage.
    "STORAGE": "default",
    "OUTPUT_PATH": "pwa/assets",

    # Icon generation.
    "PURPOSES": ("any", "maskable"),
    "INCLUDE_LEGACY_SIZES": False,
    "BACKGROUND_COLOR": None,
    "PADDING_RATIO": 0.05,
    "MASKABLE_SAFE_AREA": 0.80,
    "MONOCHROME_THRESHOLD": 128,
    "OPAQUE": False,

    # Splash screens.
    "SPLASH_BACKGROUND_COLOR": None,
    "SPLASH_LOGO_RATIO": 0.25,
    "SPLASH_PORTRAIT_ONLY": False,
    "SPLASH_MIN_IOS": None,
    "SPLASH_DARK_BACKGROUND": None,

    # Output format.
    "OUTPUT_FORMAT": "png",
    "JPEG_QUALITY": 80,

    # Engine tuning.
    "IMAGE_PRESCALE_MAX": 800,
    "MAX_CONCURRENT_UPLOADS": 5,

    # Cache.
    "CACHE_NAME": "default",
    "CACHE_TIMEOUT": 86_400 * 12,  # 12 days in seconds.
}


def setting(key: str, override: Any = _UNSET) -> Any:
    """Resolves a single configuration value using the priority chain.

    Priority order (highest to lowest):

    1. *override* — explicit runtime value passed by the caller.
    2. ``PWA_ASSETS`` dict in Django's ``settings.py``.
    3. :data:`DEFAULTS` — built-in defaults defined in this module.

    ``None`` and ``""`` are treated as *"not provided"* and fall through
    to the next level.  This means callers can safely pass optional
    function arguments directly as *override* without ``if``-guarding them.

    Args:
        key:      Configuration key.  Must be present in :data:`DEFAULTS`.
        override: Runtime override value.  Omit entirely (or pass ``None``)
                  to skip this level.

    Returns:
        The resolved value, or ``None`` when the key is absent from all
        three levels.

    Example::

        setting("OUTPUT_PATH")                     # "pwa/icons"
        setting("OUTPUT_PATH", override="custom")  # "custom"
        setting("OUTPUT_PATH", override=None)      # "pwa/icons"  (falls through)
        setting("BACKGROUND_COLOR")                # None          (no default)
    """
    # Level 1 — runtime override (skip if not provided, None, or "").
    if override is not _UNSET and override is not None and override != "":
        return override

    # Level 2 — project settings.
    project_settings: dict[str, Any] = getattr(
        django_settings, "PWA_ASSETS", {})
    val = project_settings.get(key)
    if val is not None and val != "":
        return val

    # Level 3 — built-in defaults.
    return DEFAULTS.get(key)
