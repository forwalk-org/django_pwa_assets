from PIL import Image
from django.test import TestCase
from django_pwa_assets.generators.favicons import generate_favicons

class FaviconsGeneratorTest(TestCase):
    def test_generate(self):
        img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        tasks = list(generate_favicons(img, "pwa/test"))
        # 1 ico + 2 png = 3 tasks
        self.assertEqual(len(tasks), 3)
        ico = [t for t in tasks if t.filename.endswith(".ico")]
        self.assertEqual(len(ico), 1)
        self.assertEqual(ico[0].mimetype, "image/x-icon")
