import io
from pathlib import Path
from unittest import mock
from PIL import Image
from django.test import TestCase, override_settings
from django_pwa_assets.source import (
    compute_image_key,
    is_svg,
    optimize_svg,
    read_path,
    resolve_source_to_bytes,
    resolve_source_to_pil,
)


class SourceModuleTest(TestCase):
    def test_resolve_bytes(self):
        data = b"fake-data"
        raw, ext = resolve_source_to_bytes(data)
        self.assertEqual(raw, data)
        self.assertEqual(ext, "")

    def test_resolve_pil(self):
        img = Image.new("RGBA", (10, 10), (255, 255, 255, 255))
        raw, ext = resolve_source_to_bytes(img)
        self.assertTrue(raw.startswith(b"\x89PNG"))
        self.assertEqual(ext, ".png")

    def test_compute_key_stability(self):
        params = {"background": "#ffffff", "purposes": ["any", "maskable"]}
        key1 = compute_image_key("logo.png", params)
        key2 = compute_image_key("logo.png", params)
        self.assertEqual(key1, key2)

    def test_compute_key_param_order(self):
        # Order of list elements in params should not change the key
        key1 = compute_image_key(
            "logo.png", {"purposes": ["any", "maskable"]})
        key2 = compute_image_key(
            "logo.png", {"purposes": ["maskable", "any"]})
        self.assertEqual(key1, key2)

    def test_compute_key_ignored_params(self):
        # 'force' should be ignored
        key1 = compute_image_key("logo.png", {"background": "#fff"})
        key2 = compute_image_key(
            "logo.png", {"background": "#fff", "force": True})
        self.assertEqual(key1, key2)

    def test_read_path_restricted(self):
        with mock.patch("django_pwa_assets.source.finders.find") as mock_find:
            mock_find.return_value = None
            with mock.patch("django.core.files.storage.default_storage.exists") as mock_exists:
                mock_exists.return_value = False
                with self.assertRaises(ValueError):
                    read_path("some_random_file.png")

    def test_resolve_source_to_pil_from_bytes(self):
        # Create a small red PNG in bytes
        img = Image.new("RGB", (10, 10), "red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()

        resolved = resolve_source_to_pil(data)
        self.assertIsInstance(resolved, Image.Image)
        self.assertEqual(resolved.size, (10, 10))
        self.assertEqual(resolved.mode, "RGBA")
        self.assertEqual(resolved.getpixel((0, 0)), (255, 0, 0, 255))

    def test_resolve_source_to_pil_from_pil(self):
        img = Image.new("RGB", (5, 5), "blue")
        resolved = resolve_source_to_pil(img)
        self.assertEqual(resolved.mode, "RGBA")
        self.assertEqual(resolved.getpixel((0, 0)), (0, 0, 255, 255))

    def test_resolve_source_to_pil_from_path(self):
        img = Image.new("RGB", (1, 1), "#00FF00")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        data = buf.getvalue()

        with mock.patch("django_pwa_assets.source.read_path") as mock_read:
            mock_read.return_value = (data, ".png")
            resolved = resolve_source_to_pil("fake.png")
            self.assertEqual(resolved.getpixel((0, 0)), (0, 255, 0, 255))

    def test_is_svg_detection(self):
        self.assertTrue(is_svg(b"<?xml version='1.0'?><svg>...</svg>"))
        self.assertTrue(is_svg(b"<svg xmlns='...'>...</svg>"))
        self.assertFalse(is_svg(b"\x89PNG\r\n\x1a\n"))

    def test_optimize_svg(self):
        svg_data = b"<svg>  <g>  <rect />  </g> </svg>"
        optimized = optimize_svg(svg_data)
        # Should be different if scour works
        self.assertIsInstance(optimized, bytes)
        self.assertNotEqual(len(optimized), len(svg_data))

    def test_compute_key_strength_bytes(self):
        # Different bytes content must yield different keys
        params = {}
        key1 = compute_image_key(b"content-a", params)
        key2 = compute_image_key(b"content-b", params)
        self.assertNotEqual(key1, key2)

    def test_compute_key_strength_pil(self):
        # Different pixel data must yield different keys for the same size/mode
        img1 = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        img2 = Image.new("RGBA", (10, 10), (0, 255, 0, 255))
        params = {}
        key1 = compute_image_key(img1, params)
        key2 = compute_image_key(img2, params)
        self.assertNotEqual(key1, key2)

    def test_compute_key_prefix_storage(self):
        class MockStorage1:
            pass

        class MockStorage2:
            pass

        params = {}
        # Use a simple object with a 'storage' attribute

        class MockInput:
            def __init__(self, name, st):
                self.name = name
                self.storage = st

            def __str__(self):
                return self.name

        obj1 = MockInput("logo.png", MockStorage1())
        obj2 = MockInput("logo.png", MockStorage2())

        key1 = compute_image_key(obj1, params)
        key2 = compute_image_key(obj2, params)
        self.assertNotEqual(key1, key2)

    def test_resolve_source_to_pil_with_svg(self):
        svg_data = b"<svg><rect width='10' height='10' fill='red'/></svg>"

        # Mock cairosvg since it might be missing
        with mock.patch("django_pwa_assets.source.cairosvg") as mock_cairo:
            if mock_cairo:
                # Mock svg2png to return a fake PNG
                fake_img = Image.new("RGBA", (10, 10), "red")
                buf = io.BytesIO()
                fake_img.save(buf, format="PNG")
                mock_cairo.svg2png.return_value = buf.getvalue()

            resolved = resolve_source_to_pil(svg_data)
            self.assertEqual(resolved.mode, "RGBA")
            self.assertTrue(hasattr(resolved, "svg_source"))
            self.assertIsNotNone(resolved.svg_source)
            self.assertIn(b"<svg", resolved.svg_source)
