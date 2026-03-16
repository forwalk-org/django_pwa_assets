from PIL import Image
from django.test import TestCase
from django_pwa_assets.generators.mstiles import generate_mstiles

class MstilesGeneratorTest(TestCase):
    def test_generate(self):
        img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        tasks = list(generate_mstiles(img, "pwa/test"))
        # 4 specs
        self.assertEqual(len(tasks), 4)
        self.assertTrue(tasks[0].filename.startswith("pwa/test/mstile-"))
        self.assertIn("name", tasks[0].metadata)
