"""Template tags for automatic PWA asset injection (icons, splash screens, meta).

This module provides Django template tags that drive the full PWA asset
pipeline.  Generation is delegated to :mod:`..generator`; HTML rendering
is handled by Django templates in ``django_pwa_assets/templates/``.

The template-based rendering approach means the HTML output is fully
overridable by any project that adds its own
``templates/django_pwa_assets/<tag>.html`` file, without touching Python.

Template lookup order (standard Django):

1. Project-level ``templates/django_pwa_assets/<tag>.html``
2. Package-level ``django_pwa_assets/templates/django_pwa_assets/<tag>.html``

Public template tags:
    - ``{% pwa_icons %}``        — standard + maskable icon ``<link>`` tags.
    - ``{% pwa_icon_entries %}`` — raw entries list for custom rendering.
    - ``{% pwa_favicons %}``     — favicon ``<link>`` tags.
    - ``{% pwa_mstiles %}``      — Windows Tile ``<meta>`` tags.
    - ``{% pwa_splashes %}``     — iOS splash screen ``<link>`` tags.
    - ``{% pwa_head_tags %}``    — all-in-one tag; single cache round-trip
      via :func:`~..generator.get_or_generate_all`.

Example::

    {% load pwa_assets %}
    {% pwa_head_tags "icons/logo.svg" background="#ffffff" %}
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django import template
from django.utils.html import mark_safe

from ..conf import setting
from ..generator import (
    AssetManifestEntry,
    get_or_generate_all,
    get_or_generate_favicons,
    get_or_generate_icons,
    get_or_generate_mstiles,
    get_or_generate_splashes,
)

register = template.Library()
logger = logging.getLogger(__name__)

# Template paths — override any of these in your project's templates dir.
_TPL_ICONS    = "django_pwa_assets/icons.html"
_TPL_FAVICONS = "django_pwa_assets/favicons.html"
_TPL_SPLASHES = "django_pwa_assets/splashes.html"
_TPL_MSTILES  = "django_pwa_assets/mstiles.html"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _kw(**kwargs: Any) -> Dict[str, Any]:
    """Strips empty strings and ``None`` values from template kwargs.

    ``0``, ``False``, and other falsy-but-meaningful values are preserved.

    Args:
        **kwargs: Raw keyword arguments captured by a template tag.

    Returns:
        Filtered dictionary with ``None`` and ``""`` values removed.

    Example::

        _kw(background="#fff", padding_ratio=None, opaque=False)
        # {"background": "#fff", "opaque": False}
    """
    return {k: v for k, v in kwargs.items() if v is not None and v != ""}


def _is_bool(val: Any) -> bool:
    """Interprets a template-supplied value as a boolean.

    Accepts actual booleans, integers, and common string representations
    (``"true"``, ``"1"``, ``"yes"``, ``"on"``).

    Args:
        val: Value to check — string, bool, or int.

    Returns:
        ``True`` when *val* is considered truthy.

    Example::

        _is_bool("true")   # True
        _is_bool("0")      # False
        _is_bool(True)     # True
    """
    if isinstance(val, bool):
        return val
    return str(val).lower() in ("true", "1", "yes", "on")


def _resolve_img(img: Any) -> Any:
    """Returns *img* when truthy, otherwise falls back to ``DEFAULT_IMAGE``.

    Args:
        img: Caller-supplied image source (may be empty string or ``None``).

    Returns:
        Resolved image source, or ``None`` when no source is available.

    Example::

        _resolve_img(None)        # setting("DEFAULT_IMAGE") or None
        _resolve_img("logo.svg")  # "logo.svg"
    """
    return img or setting("DEFAULT_IMAGE")


def _render(template_name: str, context: Dict[str, Any]) -> str:
    """Renders a PWA asset template and returns a mark-safe string.

    Args:
        template_name: Django template path relative to the templates root.
        context: Template context dict.

    Returns:
        Mark-safe rendered HTML string.
    """
    from django.template.loader import render_to_string
    return mark_safe(render_to_string(template_name, context))


def _icons_html(entries: List[Dict[str, Any]], theme_color: Optional[str] = None) -> str:
    """Internal helper for icons HTML generation (kept for test compatibility)."""
    return _render(_TPL_ICONS, {"entries": entries, "theme_color": theme_color})


# ---------------------------------------------------------------------------
# Template tags
# ---------------------------------------------------------------------------


@register.simple_tag
def pwa_icons(img: Any = None, **kwargs: Any) -> str:
    """Renders ``<link>`` tags for the full PWA icon set.

    Uses ``django_pwa_assets/icons.html``.  Override this template in your
    project to customise the output without modifying the package.

    Args:
        img: Image source.  Falls back to ``DEFAULT_IMAGE``.
        **kwargs: Forwarded to :func:`~..generator.get_or_generate_icons`.
            The special key ``theme_color`` is consumed here and passed to
            the template context; it is not forwarded to the generator.

    Returns:
        Mark-safe HTML string, or ``<!-- pwa_icons: img required -->`` when
        no source is available.

    Example::

        {% pwa_icons "logo.svg" background="#ffffff" theme_color="#5bbad5" %}
    """
    resolved = _resolve_img(img)
    if not resolved:
        return mark_safe("<!-- pwa_icons: img required -->")

    kw = _kw(**kwargs)
    theme_color = kw.pop("theme_color", None)
    entries = get_or_generate_icons(resolved, **kw)
    return _render(_TPL_ICONS, {"entries": entries, "theme_color": theme_color})


@register.simple_tag
def pwa_icon_entries(img: Any = None, **kwargs: Any) -> List[AssetManifestEntry]:
    """Returns the raw icon entries list for custom rendering.

    Useful when the caller needs full control over the HTML, for example
    inside a Web App Manifest JSON response or a custom template tag.

    Args:
        img: Image source.  Falls back to ``DEFAULT_IMAGE``.
        **kwargs: Forwarded to :func:`~..generator.get_or_generate_icons`.

    Returns:
        List of :class:`~..generator.AssetManifestEntry` dicts, or ``[]``
        when no source is available.

    Example::

        {% pwa_icon_entries "logo.svg" as entries %}
    """
    resolved = _resolve_img(img)
    if not resolved:
        return []
    return get_or_generate_icons(resolved, **_kw(**kwargs))


@register.simple_tag
def pwa_favicons(img: Any = None, **kwargs: Any) -> str:
    """Renders ``<link>`` tags for the classic favicon and PNG variants.

    Uses ``django_pwa_assets/favicons.html``.

    Args:
        img: Image source.  Falls back to ``DEFAULT_IMAGE``.
        **kwargs: Forwarded to :func:`~..generator.get_or_generate_favicons`.

    Returns:
        Mark-safe HTML string, or empty string when no source is available.

    Example::

        {% pwa_favicons "logo.svg" %}
    """
    resolved = _resolve_img(img)
    if not resolved:
        return mark_safe("")

    entries = get_or_generate_favicons(resolved, **_kw(**kwargs))
    return _render(_TPL_FAVICONS, {"entries": entries})


@register.simple_tag
def pwa_mstiles(img: Any = None, **kwargs: Any) -> str:
    """Renders ``<meta>`` tags for Windows Tiles.

    Uses ``django_pwa_assets/mstiles.html``.

    Args:
        img: Image source.  Falls back to ``DEFAULT_IMAGE``.
        **kwargs: Forwarded to :func:`~..generator.get_or_generate_mstiles`.
            The special key ``tile_color`` is consumed here and passed to
            the template context; it is not forwarded to the generator.

    Returns:
        Mark-safe HTML string, or empty string when no source is available.

    Example::

        {% pwa_mstiles "logo.svg" tile_color="#2d89ef" %}
    """
    resolved = _resolve_img(img)
    if not resolved:
        return mark_safe("")

    kw = _kw(**kwargs)
    tile_color = kw.pop("tile_color", None)
    entries = get_or_generate_mstiles(resolved, **kw)
    return _render(_TPL_MSTILES, {"entries": entries, "tile_color": tile_color})


@register.simple_tag
def pwa_splashes(img: Any = None, **kwargs: Any) -> str:
    """Renders ``<link>`` tags for iOS splash screens.

    Uses ``django_pwa_assets/splashes.html``.

    Args:
        img: Image source.  Falls back to ``DEFAULT_IMAGE``.
        **kwargs: Forwarded to :func:`~..generator.get_or_generate_splashes`.

    Returns:
        Mark-safe HTML string, or empty string when no source is available.

    Example::

        {% pwa_splashes "logo.svg" background="#000000" %}
    """
    resolved = _resolve_img(img)
    if not resolved:
        return mark_safe("")

    entries = get_or_generate_splashes(resolved, **_kw(**kwargs))
    return _render(_TPL_SPLASHES, {"entries": entries})


@register.simple_tag
def pwa_head_tags(img: Any = None, **kwargs: Any) -> str:
    """All-in-one tag that injects the full PWA asset set into ``<head>``.

    Uses :func:`~..generator.get_or_generate_all` to retrieve all asset
    categories with a single cache round-trip, then renders each category
    with its own template.

    Args:
        img: Image source.  Falls back to ``DEFAULT_IMAGE``.
        **kwargs: Configuration parameters forwarded to each generator.
            Special keys consumed here and passed to template contexts:

            - ``with_splashes`` (bool) — include splash screens
              (default ``True``).
            - ``with_favicons`` (bool) — include favicons (default ``True``).
            - ``with_mstiles`` (bool)  — include MS Tiles (default ``False``).
            - ``theme_color`` (str)    — ``color`` attribute for
              ``rel="mask-icon"`` tags.
            - ``tile_color`` (str)     — ``msapplication-TileColor`` value.

    Returns:
        Mark-safe HTML string combining all enabled asset sections, or empty
        string when no source is available.

    Example::

        {% pwa_head_tags "logo.svg" background="#fff" with_mstiles="true" %}
    """
    resolved = _resolve_img(img)
    if not resolved:
        return mark_safe("")

    with_splashes: bool = _is_bool(kwargs.pop("with_splashes", True))
    with_favicons: bool = _is_bool(kwargs.pop("with_favicons", True))
    with_mstiles: bool  = _is_bool(kwargs.pop("with_mstiles", False))
    theme_color: Optional[str] = kwargs.pop("theme_color", None)
    tile_color: Optional[str]  = kwargs.pop("tile_color", None)

    kw = _kw(**kwargs)

    assets = get_or_generate_all(
        resolved,
        with_favicons=with_favicons,
        with_splashes=with_splashes,
        with_mstiles=with_mstiles,
        **kw,
    )

    # Use _render() consistently with every other tag in this module so
    # that mark_safe is always applied at the same level and future edits
    # cannot accidentally forget to wrap additional fragments.
    parts: List[str] = [
        _render(_TPL_ICONS, {
            "entries": assets["icons"],
            "theme_color": theme_color,
        }),
    ]

    if with_favicons:
        parts.append(_render(_TPL_FAVICONS, {
            "entries": assets["favicons"],
        }))

    if with_splashes:
        parts.append(_render(_TPL_SPLASHES, {
            "entries": assets["splashes"],
        }))

    if with_mstiles:
        parts.append(_render(_TPL_MSTILES, {
            "entries": assets["mstiles"],
            "tile_color": tile_color,
        }))

    return mark_safe("\n".join(p for p in parts if p.strip()))
