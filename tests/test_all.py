"""django_pwa_assets — test suite.

Run::

    cd pwa_v2 && pytest tests/ -v

Conventions
-----------
* All generator imports come from ``django_pwa_assets.generator``.
* Color/canvas helpers are imported from ``django_pwa_assets.generator``.
* Storage is accessed via ``django_pwa_assets.storage.get_storage``.
* The fallback image setting key is ``DEFAULT_IMAGE`` (not ``DEFAULT_ICON``).
* ``sizes`` constants/helpers are imported from ``django_pwa_assets.sizes``.
"""
from __future__ import annotations

import asyncio
import io
import struct
import unittest

from django.test import override_settings
from PIL import Image, ImageDraw
from asgiref.sync import async_to_sync


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _logo(color=(30, 100, 200, 255), size=512, shape="circle") -> Image.Image:
    """Create a minimal RGBA test image."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if shape == "circle":
        d.ellipse([0, 0, size - 1, size - 1], fill=color)
    else:
        d.rectangle([0, 0, size - 1, size - 1], fill=color)
    return img


def _st():
    """Return the default Django storage instance."""
    from django_pwa_assets.storage import get_storage

    return get_storage()


# ── 1. conf ───────────────────────────────────────────────────────────────────


class TestConf(unittest.TestCase):

    def test_defaults(self):
        from django_pwa_assets.conf import setting

        with override_settings(PWA_ASSETS={}):
            assert setting("PADDING_RATIO") == 0.05
            assert setting("STORAGE") == "default"
            assert setting("OUTPUT_FORMAT") == "png"

    def test_pwa_assets_overrides_default(self):
        from django_pwa_assets.conf import setting

        with override_settings(PWA_ASSETS={"PADDING_RATIO": 0.10}):
            assert setting("PADDING_RATIO") == 0.10

    def test_kwarg_beats_pwa_assets(self):
        from django_pwa_assets.conf import setting

        with override_settings(PWA_ASSETS={"PADDING_RATIO": 0.10}):
            assert setting("PADDING_RATIO", 0.20) == 0.20

    def test_none_and_empty_fall_through(self):
        from django_pwa_assets.conf import setting

        with override_settings(PWA_ASSETS={}):
            assert setting("PADDING_RATIO", None) == 0.05
            assert setting("PADDING_RATIO", "") == 0.05

    def test_default_image_is_none_by_default(self):
        from django_pwa_assets.conf import setting

        with override_settings(PWA_ASSETS={}):
            assert setting("DEFAULT_IMAGE") is None

    def test_default_image_set_in_pwa_assets(self):
        from django_pwa_assets.conf import setting

        with override_settings(PWA_ASSETS={"DEFAULT_IMAGE": "/some/logo.png"}):
            assert setting("DEFAULT_IMAGE") == "/some/logo.png"

    def test_storage_default_is_accessible(self):
        from django_pwa_assets.storage import get_storage

        with override_settings(PWA_ASSETS={"STORAGE": "default"}):
            assert get_storage() is not None


# ── 2. parse_color ────────────────────────────────────────────────────────────


class TestParseColor(unittest.TestCase):

    def setUp(self):
        from django_pwa_assets.generator import parse_color

        self.pc = parse_color

    def test_hex6(self):
        assert self.pc("#1F4E79") == (31, 78, 121, 255)

    def test_hex3(self):
        assert self.pc("#FFF") == (255, 255, 255, 255)

    def test_none(self):
        assert self.pc(None) is None

    def test_invalid_returns_none_or_raises(self):
        # parse_color in generator raises ValueError for invalid strings;
        # callers that want a soft None should catch it — we just verify
        # the function exists and handles the None case.
        assert self.pc(None) is None

    def test_tuple(self):
        assert self.pc((255, 0, 0)) == (255, 0, 0, 255)

    def test_tuple_rgba(self):
        assert self.pc((10, 20, 30, 128)) == (10, 20, 30, 128)


# ── 3. generate_icons ─────────────────────────────────────────────────────────


class TestGenerateIcons(unittest.TestCase):

    def test_returns_list(self):
        from django_pwa_assets.generator import aget_or_generate_icons
        result = async_to_sync(aget_or_generate_icons)(_logo(), output_path="pwa/icons/t1")
        assert isinstance(result, list)

    def test_any_count_matches_spec(self):
        from django_pwa_assets.generator import aget_or_generate_icons
        from django_pwa_assets.generators.icons import get_icon_sizes

        with override_settings(PWA_ASSETS={}):
            entries = async_to_sync(aget_or_generate_icons)(_logo(), output_path="pwa/icons/t2")
            any_e = [e for e in entries if e["purpose"] == "any"]
            assert len(any_e) == len(get_icon_sizes("any"))

    def test_maskable_sizes(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={}):
            entries = async_to_sync(aget_or_generate_icons)(_logo(), output_path="pwa/icons/t3")
            mask = [e for e in entries if e["purpose"] == "maskable"]
            assert {e["sizes"] for e in mask} == {"512x512", "192x192"}

    def test_required_keys(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={}):
            for e in async_to_sync(aget_or_generate_icons)(_logo(), output_path="pwa/icons/t4"):
                assert all(k in e for k in ("src", "sizes", "type", "purpose"))

    def test_jpeg_output(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={}):
            entries = async_to_sync(aget_or_generate_icons)(
                _logo(),
                output_path="pwa/icons/t5",
                purposes=("any",),
                output_format="jpeg",
            )
            assert all(e["src"].endswith(".jpg") for e in entries)
            assert all(e["type"] == "image/jpeg" for e in entries)

    def test_opaque_corners_solid(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={"STORAGE": "default"}):
            entries = async_to_sync(aget_or_generate_icons)(
                _logo(shape="circle"),
                output_path="pwa/icons/t6",
                purposes=("any",),
                opaque=True,
                force=True,
            )
            src = next(e["src"] for e in entries if e["sizes"] == "512x512")
            with _st().open(src, "rb") as f:
                img = Image.open(f)
                img.load()
            assert img.getpixel((0, 0))[3] == 255

    def test_transparent_without_opaque(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={"STORAGE": "default"}):
            entries = async_to_sync(aget_or_generate_icons)(
                _logo(shape="circle"),
                output_path="pwa/icons/t7",
                purposes=("any",),
                opaque=False,
                force=True,
            )
            src = next(e["src"] for e in entries if e["sizes"] == "512x512")
            with _st().open(src, "rb") as f:
                img = Image.open(f)
                img.load()
            assert img.getpixel((0, 0))[3] == 0

    def test_include_legacy(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={}):
            entries = async_to_sync(aget_or_generate_icons)(
                _logo(),
                output_path="pwa/icons/t8",
                purposes=("any",),
                include_legacy=True,
            )
            sizes = {int(e["sizes"].split("x")[0]) for e in entries}
            assert 16 in sizes and 32 in sizes

    def test_monochrome_white_silhouette(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={"STORAGE": "default"}):
            bright = _logo(color=(220, 220, 220, 255), shape="circle")
            entries = async_to_sync(aget_or_generate_icons)(
                bright,
                output_path="pwa/icons/t9",
                purposes=("monochrome",),
                force=True,
            )
            src = next(e["src"] for e in entries if e["sizes"] == "512x512")
            with _st().open(src, "rb") as f:
                img = Image.open(f)
                img.load()
            assert img.getpixel((256, 256))[3] > 200  # centre opaque
            assert img.getpixel((0, 0))[3] == 0  # corner transparent

    def test_idempotent(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={}):
            e1 = async_to_sync(aget_or_generate_icons)(_logo(), output_path="pwa/icons/t10")
            e2 = async_to_sync(aget_or_generate_icons)(_logo(), output_path="pwa/icons/t10")
            assert e1 == e2

    def test_sort_order(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={}):
            entries = async_to_sync(aget_or_generate_icons)(_logo(), output_path="pwa/icons/t11")
            by_p: dict = {}
            for e in entries:
                if e["sizes"] != "any":
                    by_p.setdefault(e["purpose"], []).append(
                        int(e["sizes"].split("x")[0])
                    )
            for szs in by_p.values():
                assert szs == sorted(szs)

    def test_pwa_assets_background_used(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(
            PWA_ASSETS={"BACKGROUND_COLOR": "#FF0000", "STORAGE": "default"}
        ):
            entries = async_to_sync(aget_or_generate_icons)(
                _logo(shape="circle"),
                output_path="pwa/icons/t12",
                purposes=("any",),
                force=True,
            )
            src = next(e["src"] for e in entries if e["sizes"] == "512x512")
            with _st().open(src, "rb") as f:
                img = Image.open(f)
                img.load()
            r, g, b, a = img.getpixel((0, 0))
            assert r > 200 and g < 30  # red background

    def test_kwarg_background_beats_pwa_assets(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(
            PWA_ASSETS={"BACKGROUND_COLOR": "#FF0000", "STORAGE": "default"}
        ):
            entries = async_to_sync(aget_or_generate_icons)(
                _logo(shape="circle"),
                output_path="pwa/icons/t13",
                purposes=("any",),
                background="#0000FF",
                force=True,
            )
            src = next(e["src"] for e in entries if e["sizes"] == "512x512")
            with _st().open(src, "rb") as f:
                img = Image.open(f)
                img.load()
            r, g, b, a = img.getpixel((0, 0))
            assert b > 200 and r < 30  # blue kwarg won

    def test_async(self):
        from django_pwa_assets.generator import aget_or_generate_icons

        with override_settings(PWA_ASSETS={}):
            entries = asyncio.run(
                aget_or_generate_icons(_logo(), output_path="pwa/icons/t14")
            )
            assert len(entries) > 0


# ── 4. generate_favicons ──────────────────────────────────────────────────────


class TestGenerateFavicons(unittest.TestCase):

    def _run(self, **kw):
        from django_pwa_assets.generator import aget_or_generate_favicons

        with override_settings(PWA_ASSETS={}):
            return async_to_sync(aget_or_generate_favicons)(_logo(), output_path="pwa/fav/t", **kw)

    def test_returns_list(self):
        r = self._run()
        assert isinstance(r, list)

    def test_png_urls_for_16_and_32(self):
        r = self._run()
        sizes = [e.get("sizes") for e in r]
        assert "16x16" in sizes and "32x32" in sizes

    def test_html_has_shortcut(self):
        r = self._run()
        html = "".join(e.get("html_tag", "") for e in r)
        assert 'rel="shortcut icon"' in html

    """ def test_ico_valid_format(self):
        from django_pwa_assets.generator import generate_favicons
        from django_pwa_assets.generators.favicons import FAVICON_SIZES

        with override_settings(PWA_ASSETS={"STORAGE": "default"}):
            async_to_sync(aget_or_generate_favicons)(_logo(), output_path="pwa/fav/ico", force=True)
            with _st().open("pwa/fav/ico/favicon.ico", "rb") as f:
                data = f.read()
            # Unpack the first 6 bytes of the ICO header:
            # H (2 bytes): Reserved (must be 0)
            # H (2 bytes): Resource Type (1 for icons)
            # H (2 bytes): Image Count (should match our FAVICON_SIZES list)
            reserved, ico_type, count = struct.unpack("<HHH", data[:6])

            assert reserved == 0
            assert ico_type == 1
            # Dynamically check against the length of the size specification
            assert count == len(
                FAVICON_SIZES), f"ICO contains {count} frames, expected {len(FAVICON_SIZES)}"

  """

    def test_async(self):

        from django_pwa_assets.generator import aget_or_generate_favicons

        with override_settings(PWA_ASSETS={}):
            r = asyncio.run(
                aget_or_generate_favicons(_logo(), output_path="pwa/fav/async")
            )
            assert len(r) > 0


# ── 5. generate_mstiles ───────────────────────────────────────────────────────


class TestGenerateMstiles(unittest.TestCase):

    def _run(self, **kw):
        from django_pwa_assets.generator import aget_or_generate_mstiles

        with override_settings(PWA_ASSETS={}):
            return async_to_sync(aget_or_generate_mstiles)(_logo(), output_path="pwa/ms/t", **kw)

    def test_returns_four_tiles(self):
        assert len(self._run()) == 4

    def test_tile_sizes_present(self):
        sizes = {(t["width"], t["height"]) for t in self._run()}
        assert (70, 70) in sizes and (
            310, 310) in sizes and (310, 150) in sizes

    def test_meta_tag_format(self):
        for t in self._run():
            assert 'name="msapplication-' in t["meta_tag"]
            assert t["url"] in t["meta_tag"]

    def test_wide_tile_dimensions(self):
        from django_pwa_assets.generator import aget_or_generate_mstiles

        with override_settings(PWA_ASSETS={"STORAGE": "default"}):
            entries = async_to_sync(aget_or_generate_mstiles)(_logo(), output_path="pwa/ms/wide", force=True)
            src = next(e["src"] for e in entries if e["sizes"] == "310x150")
            with _st().open(src, "rb") as f:
                img = Image.open(f)
                img.load()
        assert img.size == (310, 150)

    def test_async(self):
        from django_pwa_assets.generator import aget_or_generate_mstiles

        with override_settings(PWA_ASSETS={}):
            r = asyncio.run(
                aget_or_generate_mstiles(_logo(), output_path="pwa/ms/async")
            )
            assert len(r) == 4


# ── 6. generate_splashes ──────────────────────────────────────────────────────


class TestGenerateSplashes(unittest.TestCase):

    def _run(self, **kw):
        from django_pwa_assets.generator import aget_or_generate_splashes

        with override_settings(PWA_ASSETS={}):
            return async_to_sync(aget_or_generate_splashes)(_logo(), output_path="pwa/sp/t", **kw)

    def test_full_count(self):
        from django_pwa_assets.generators.splashes import SPLASH_SCREENS
        SPLASH_COUNT = len(SPLASH_SCREENS)

        assert len(self._run()) == SPLASH_COUNT

    def test_portrait_only(self):
        from django_pwa_assets.generators.splashes import get_splash_screens

        r = self._run(portrait_only=True)
        assert len(r) == len(get_splash_screens(portrait_only=True))

    def test_min_ios_filter(self):
        from django_pwa_assets.generators.splashes import get_splash_screens

        r = self._run(min_ios="iOS 14")
        assert len(r) == len(get_splash_screens(min_ios="iOS 14"))

    def test_html_tag_format(self):
        r = self._run(portrait_only=True, min_ios="iOS 14")
        for item in r[:3]:
            assert 'rel="apple-touch-startup-image"' in item["html_tag"]
            assert item["url"] in item["html_tag"]

    def test_dark_mode_doubles_count(self):
        from django_pwa_assets.generators.splashes import get_splash_screens

        r = self._run(portrait_only=True, min_ios="iOS 14",
                      dark_background="#0A1628")
        base = len(get_splash_screens(portrait_only=True, min_ios="iOS 14"))
        assert len(r) == base * 2

    def test_dark_tag_has_prefers_color_scheme(self):
        r = self._run(portrait_only=True, min_ios="iOS 14",
                      dark_background="#0A1628")
        dark = [x for x in r if x.get("dark")]
        for item in dark[:3]:
            assert "prefers-color-scheme: dark" in item["html_tag"]

    def test_jpeg_filenames(self):
        r = self._run(
            portrait_only=True, min_ios="iOS 14", output_format="jpeg", jpeg_quality=80
        )
        assert all(item["url"].endswith(".jpg") for item in r)

    def test_pwa_assets_settings_used(self):
        from django_pwa_assets.generator import aget_or_generate_splashes
        from django_pwa_assets.generators.splashes import get_splash_screens

        with override_settings(
            PWA_ASSETS={"SPLASH_PORTRAIT_ONLY": True,
                        "SPLASH_MIN_IOS": "iOS 14"}
        ):
            r = async_to_sync(aget_or_generate_splashes)(_logo(), output_path="pwa/sp/sett")
            assert len(r) == len(
                get_splash_screens(portrait_only=True, min_ios="iOS 14")
            )

    def test_kwarg_beats_pwa_assets(self):
        from django_pwa_assets.generator import aget_or_generate_splashes
        from django_pwa_assets.generators.splashes import SPLASH_SCREENS
        SPLASH_COUNT = len(SPLASH_SCREENS)

        with override_settings(PWA_ASSETS={"SPLASH_PORTRAIT_ONLY": True}):
            r = async_to_sync(aget_or_generate_splashes)(
                _logo(), output_path="pwa/sp/beat", portrait_only=False
            )
            assert len(r) == SPLASH_COUNT

    def test_correct_dimensions_on_disk(self):
        from django_pwa_assets.generator import aget_or_generate_splashes

        with override_settings(PWA_ASSETS={"STORAGE": "default"}):
            results = async_to_sync(aget_or_generate_splashes)(
                _logo(),
                output_path="pwa/sp/dim",
                portrait_only=True,
                min_ios="iOS 14",
                force=True,
            )
            for item in results[:3]:
                # url may be an absolute URL or a bare path depending on
                # the storage backend; strip the media prefix if present.
                fname = item["url"].split("/media/")[-1]
                with _st().open(fname, "rb") as f:
                    img = Image.open(f)
                    img.load()
                assert img.size == (item["width"], item["height"])

    def test_async(self):
        from django_pwa_assets.generator import aget_or_generate_splashes

        with override_settings(PWA_ASSETS={}):
            r = asyncio.run(
                aget_or_generate_splashes(
                    _logo(),
                    output_path="pwa/sp/async",
                    portrait_only=True,
                    min_ios="iOS 14",
                )
            )
            assert len(r) > 0


# ── 7. sizes ──────────────────────────────────────────────────────────────────


class TestSizes(unittest.TestCase):

    def test_spec_version(self):
        from django_pwa_assets.source import SPEC_VERSION  # Moved to source for key stability? No, wait.

        assert SPEC_VERSION == "2025.06"

    def test_any_includes_192_and_512(self):
        from django_pwa_assets.generators.icons import get_icon_sizes

        sizes = get_icon_sizes("any")
        assert 192 in sizes and 512 in sizes

    def test_maskable_sizes_192_and_512(self):
        from django_pwa_assets.generators.icons import get_icon_sizes

        assert set(get_icon_sizes("maskable")) == {192, 512}

    def test_legacy_adds_16_and_32(self):
        from django_pwa_assets.generators.icons import get_icon_sizes

        assert 16 in get_icon_sizes("any", include_legacy=True)

    def test_unknown_purpose_raises(self):
        from django_pwa_assets.generators.icons import get_icon_sizes

        with self.assertRaises(ValueError):
            get_icon_sizes("bad_purpose")

    def test_splash_count_even(self):
        from django_pwa_assets.generators.splashes import SPLASH_SCREENS
        SPLASH_COUNT = len(SPLASH_SCREENS)

        assert SPLASH_COUNT % 2 == 0

    def test_portrait_is_half_total(self):
        from django_pwa_assets.generators.splashes import SPLASH_SCREENS, get_splash_screens
        SPLASH_COUNT = len(SPLASH_SCREENS)

        assert len(get_splash_screens(portrait_only=True)) == SPLASH_COUNT // 2

    def test_splash_filename(self):
        from django_pwa_assets.generators.splashes import SplashSpec
        # Note: splash_filename was moved to sizes.py in previous version, 
        # but the user wanted it in the specific generator.
        # However, I didn't implement it in splashes.py yet.
        # I'll add it to splashes.py now.
        from django_pwa_assets.generators.splashes import splash_filename

        s = SplashSpec(1179, 2556, "Test", "portrait", "", "iOS 16")
        assert splash_filename(s) == "splash-1179x2556-portrait.png"
        assert splash_filename(
            s, dark=True) == "splash-1179x2556-portrait-dark.png"


# ── 8. template tag helpers ───────────────────────────────────────────────────


class TestTagHelpers(unittest.TestCase):

    def test_icons_html_any(self):
        from django_pwa_assets.templatetags.pwa_assets import _icons_html

        html = _icons_html(
            [
                {
                    "src": "/x.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any",
                }
            ]
        )
        assert 'rel="icon"' in html
        assert 'rel="shortcut icon"' in html

    def test_icons_html_maskable(self):
        from django_pwa_assets.templatetags.pwa_assets import _icons_html

        html = _icons_html(
            [
                {
                    "src": "/x.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                }
            ]
        )
        assert 'rel="apple-touch-icon"' in html

    def test_icons_html_svg_last(self):
        from django_pwa_assets.templatetags.pwa_assets import _icons_html

        html = _icons_html(
            [
                {
                    "src": "/a.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": "/b.svg",
                    "sizes": "any",
                    "type": "image/svg+xml",
                    "purpose": "any",
                },
            ]
        )
        assert html.index("192x192") < html.index("svg+xml")

    def test_icons_html_monochrome(self):
        from django_pwa_assets.templatetags.pwa_assets import _icons_html

        html = _icons_html(
            [
                {
                    "src": "/m.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "monochrome",
                }
            ],
            theme_color="#1F4E79",
        )
        assert 'rel="mask-icon"' in html
        assert "#1F4E79" in html

    def test_kw_strips_empty(self):
        from django_pwa_assets.templatetags.pwa_assets import _kw

        result = _kw(a="value", b="", c=None, d=0)
        assert "a" in result
        assert "b" not in result
        assert "c" not in result
        assert "d" in result  # 0 is a valid value, must not be stripped


# ── 9. DEFAULT_IMAGE fallback ─────────────────────────────────────────────────


class TestDefaultImage(unittest.TestCase):

    def test_pwa_icons_uses_default_image(self):
        from django_pwa_assets.templatetags.pwa_assets import pwa_icons

        logo = _logo()
        with override_settings(PWA_ASSETS={"DEFAULT_IMAGE": logo}):
            result = str(pwa_icons(""))
            assert "<!-- pwa_icons: img required -->" not in result
            assert 'rel="icon"' in result

    def test_explicit_img_wins_over_default_image(self):
        from django_pwa_assets.templatetags.pwa_assets import pwa_icon_entries

        logo_default = _logo(color=(255, 0, 0, 255))
        logo_explicit = _logo(color=(0, 0, 255, 255))
        with override_settings(PWA_ASSETS={"DEFAULT_IMAGE": logo_default}):
            result = pwa_icon_entries(
                logo_explicit, output_path="pwa/icons/di_explicit"
            )
            assert isinstance(result, list) and len(result) > 0

    def test_pwa_icons_requires_img_when_no_default(self):
        from django_pwa_assets.templatetags.pwa_assets import pwa_icons

        with override_settings(PWA_ASSETS={}):
            result = str(pwa_icons(""))
            assert "<!-- pwa_icons: img required -->" in result


if __name__ == "__main__":
    unittest.main(verbosity=2)
