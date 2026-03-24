import pytest
from PIL import Image
from django.test import TestCase
from django_pwa_assets.generator import (
    aget_or_create_manifest_icon,
    get_or_create_manifest_icons,
)

class GenerateIconsManifestTest(TestCase):
    def setUp(self):
        self.img = Image.new("RGBA", (512, 512), (255, 0, 0, 255))

    def test_aget_or_create_manifest_icon(self):
        from asgiref.sync import async_to_sync
        icons = async_to_sync(aget_or_create_manifest_icon)(self.img, purposes=["any"])
        
        # 'any' purpose generates 10 sizes by default
        assert len(icons) == 10
        for icon in icons:
            assert "src" in icon
            assert "sizes" in icon
            assert "type" in icon
            assert "purpose" in icon
            assert icon["purpose"] == "any"
            assert icon["type"] == "image/png"
            assert "x" in icon["sizes"]
            # src should be a URL (starts with /media/ or similar in default test settings)
            assert icon["src"].startswith("/")

    def test_get_or_create_manifest_icons(self):
        icons = get_or_create_manifest_icons(self.img, purposes=["maskable"])
        
        # 'maskable' purpose generates 2 sizes by default (192, 512)
        assert len(icons) == 2
        for icon in icons:
            assert "src" in icon
            assert "sizes" in icon
            assert "type" in icon
            assert "purpose" in icon
            assert icon["purpose"] == "maskable"
            assert icon["type"] == "image/png"
            assert icon["sizes"] in ["192x192", "512x512"]
