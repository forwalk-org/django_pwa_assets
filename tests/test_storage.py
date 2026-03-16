import posixpath
import unittest
from django_pwa_assets.storage import (
    get_storage,
    get_manifest,
    set_manifest,
    delete_manifest,
    storage_assets_exist
)

from django.core.files.base import ContentFile

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.st = get_storage()
        self.asset_dir = "test_pwa_storage"
        self.manifest_path = posixpath.join(self.asset_dir, "manifest.json")
        
        # Clean up
        delete_manifest(self.asset_dir)

    def test_cache_set_get(self):
        entries = [{"src": "test.png", "url": "/test.png"}]
        set_manifest(self.asset_dir, entries)
        
        # Should be in storage
        self.assertTrue(self.st.exists(self.manifest_path))
        
        # Should be retrievable
        retrieved = get_manifest(self.asset_dir)
        self.assertEqual(retrieved[0]["src"], "test.png")
        self.assertIn("generated_at", retrieved[0])

    def test_cache_delete(self):
        entries = [{"src": "test.png", "url": "/test.png"}]
        set_manifest(self.asset_dir, entries)
        self.assertTrue(self.st.exists(self.manifest_path))
        
        delete_manifest(self.asset_dir)
        self.assertFalse(self.st.exists(self.manifest_path))
        self.assertIsNone(get_manifest(self.asset_dir))

    def test_storage_assets_exist(self):
        # 1. No manifest
        self.assertFalse(storage_assets_exist(self.asset_dir))
        
        # 2. Manifest exists but file missing
        entries = [{"src": "missing.png", "url": "/missing.png"}]
        set_manifest(self.asset_dir, entries)
        self.assertFalse(storage_assets_exist(self.asset_dir))
        
        # 3. Both exist
        self.st.save("missing.png", ContentFile(b"test"))
        try:
            self.assertTrue(storage_assets_exist(self.asset_dir))
        finally:
            # Cleanup
            self.st.delete("missing.png")

    def test_manifest_corrupt_fallback(self):
        # Overwrite manifest with invalid JSON
        self.st.delete(self.manifest_path)
        self.st.save(self.manifest_path, ContentFile(b"invalid json"))
        
        # Should handle corruption gracefully (return None)
        self.assertIsNone(get_manifest(self.asset_dir))
