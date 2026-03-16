from unittest import mock
from PIL import Image
from django.test import TestCase
from django_pwa_assets.generators.icons import generate_icons, get_icon_sizes

class IconsGeneratorTest(TestCase):
    def test_get_sizes(self):
        sizes = get_icon_sizes("maskable")
        self.assertEqual(sizes, (192, 512))

    def test_generate(self):
        img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        tasks = list(generate_icons(img, "pwa/test", purposes=["any"]))
        # 'any' has 10 sizes by default
        self.assertEqual(len(tasks), 10)
        self.assertTrue(tasks[0].filename.startswith("pwa/test/any-"))
        self.assertEqual(tasks[0].mimetype, "image/png")

    def test_generate_with_svg(self):
        img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        img.source_svg = b"<svg>test</svg>"
        tasks = list(generate_icons(img, "pwa/test", purposes=["any"]))
        
        # 'any' has 10 sizes + 1 for SVG
        self.assertEqual(len(tasks), 11)
        
        svg_task = [t for t in tasks if t.mimetype == "image/svg+xml"][0]
        self.assertEqual(svg_task.filename, "pwa/test/icon.svg")
        self.assertEqual(svg_task.content, b"<svg>test</svg>")
        self.assertEqual(svg_task.metadata["sizes"], "any")
        self.assertEqual(svg_task.metadata["purpose"], "any")
