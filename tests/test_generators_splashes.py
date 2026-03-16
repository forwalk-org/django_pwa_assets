from PIL import Image
from django.test import TestCase
from django_pwa_assets.generators.splashes import generate_splashes

class SplashesGeneratorTest(TestCase):
    def test_generate(self):
        img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        tasks = list(generate_splashes(img, "pwa/test", portrait_only=True))
        # 12 devices * 1 orientation = 12 tasks
        self.assertEqual(len(tasks), 12)
        self.assertTrue(tasks[0].filename.startswith("pwa/test/splash-"))
        self.assertIn("media", tasks[0].metadata)

    def test_dark_mode(self):
        img = Image.new("RGBA", (100, 100), (255, 255, 255, 255))
        tasks = list(generate_splashes(img, "pwa/test", portrait_only=True, dark_background="#000000"))
        # 12 devices * 1 orientation * 2 modes = 24 tasks
        self.assertEqual(len(tasks), 24)
        dark_tasks = [t for t in tasks if t.metadata.get("dark")]
        self.assertEqual(len(dark_tasks), 12)
