"""Low-level storage and manifest handling for PWA assets.

This module implements a manifest-driven caching architecture. Asset metadata
(filenames, types, sizes) and freshness metadata (source identity, generation
timestamp) are stored in a 'manifest.json' file within each asset directory.
"""

from __future__ import annotations

import json
import logging
import posixpath
import time
from typing import Any, Dict, List, Optional, Union

from django.core.cache import caches
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from .conf import setting

# Django storage compatibility (4.2+)
try:
    from django.core.files.storage import storages as _storages

    def get_storage_backend(alias: str):
        return _storages[alias]

except ImportError:
    from django.core.files.storage import get_storage_class

    def get_storage_backend(alias: str):
        if alias == "default":
            return default_storage
        return get_storage_class(alias)()


logger = logging.getLogger(__name__)


def get_storage() -> Any:
    """Retrieves the configured Django storage backend."""
    alias = setting("STORAGE")
    return get_storage_backend(alias)


def get_cache():
    """Returns the Django cache backend if configured."""
    cache_name = setting("CACHE_NAME")
    if not cache_name:
        return None
    return caches[cache_name]


def get_manifest_path(asset_dir: str, generator_name: str = "manifest") -> str:
    """Returns the absolute storage path for the manifest file."""
    return posixpath.join(asset_dir, f"{generator_name}.json")


def get_cache_key(asset_dir: str, generator_name: str = "manifest") -> str:
    """Returns the internal cache key for an asset directory."""
    return f"pwa_manifest:{asset_dir}:{generator_name}"


def get_manifest(asset_dir: str, generator_name: str = "manifest") -> Optional[List[Dict[str, Any]]]:
    """Retrieves asset entries, checking Django cache then storage manifest."""
    # 1. Tier 1: Django Cache
    cache = get_cache()
    if cache:
        key = get_cache_key(asset_dir, generator_name)
        cached = cache.get(key)
        if cached:
            logger.debug("PWA Cache: hit (Django) for %s:%s", asset_dir, generator_name)
            return cached

    # 2. Tier 2: Storage Manifest
    st = get_storage()
    path = get_manifest_path(asset_dir, generator_name)
    if st.exists(path):
        try:
            with st.open(path, "rb") as f:
                entries = json.loads(f.read().decode("utf-8"))
            logger.debug("PWA Cache: hit (Manifest) for %s", asset_dir)

            # Backfill Tier 1
            if cache:
                cache.set(key, entries, timeout=setting("CACHE_TIMEOUT"))

            return entries
        except (json.JSONDecodeError, UnicodeDecodeError, IOError) as e:
            logger.warning("PWA Cache: corrupt manifest at %s: %s", path, e)

    logger.debug("PWA Cache: miss for %s", asset_dir)
    return None


def set_manifest(asset_dir: str, entries: List[Dict[str, Any]], generator_name: str = "manifest") -> None:
    """Persists entries to both Django cache and storage manifest."""
    # Add generation timestamp
    timestamp = int(time.time())
    for entry in entries:
        if "generated_at" not in entry:
            entry["generated_at"] = timestamp

    # 1. Tier 1: Django Cache
    cache = get_cache()
    if cache:
        cache.set(get_cache_key(asset_dir, generator_name), entries,
                  timeout=setting("CACHE_TIMEOUT"))

    # 2. Tier 2: Storage Manifest
    st = get_storage()
    path = get_manifest_path(asset_dir, generator_name)

    if st.exists(path):
        st.delete(path)

    content = json.dumps(entries, indent=2).encode("utf-8")
    st.save(path, ContentFile(content))
    logger.debug("PWA Cache: manifest written to %s", path)


def delete_manifest(asset_dir: str, generator_name: str = "manifest") -> None:
    """Invalidates cache and removes manifest from storage."""
    cache = get_cache()
    if cache:
        cache.delete(get_cache_key(asset_dir, generator_name))

    st = get_storage()
    path = get_manifest_path(asset_dir, generator_name)
    if st.exists(path):
        st.delete(path)
        logger.debug("PWA Cache: manifest deleted at %s", path)


def storage_invalidate(asset_dir: str, generator_name: str = "manifest") -> None:
    """Public API to invalidate a specific asset directory."""
    delete_manifest(asset_dir, generator_name)


def storage_assets_exist(asset_dir: str, generator_name: str = "manifest") -> bool:
    """Checks if a valid manifest and at least one asset file exist on storage."""
    entries = get_manifest(asset_dir, generator_name)
    if not entries:
        return False

    st = get_storage()
    # Check if the first relative path in the manifest exists.
    # We only check one to avoid high latency on remote storage (S3).
    first_src = entries[0].get("src")
    if not first_src:
        return True  # Should not happen with valid manifest

    return st.exists(first_src)
