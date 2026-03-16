"""Base logic and orchestrator for PWA asset generation.

This module provides the core machinery to:
1. Render images onto canvases with background and padding.
2. Coordinate the generation and upload of multiple assets in parallel.
3. Handle asset caching and manifest persistence using Django storage.
"""

from __future__ import annotations

import asyncio
import io
import logging
import posixpath
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Tuple,
    TypedDict,
)

from PIL import Image
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile

from ..conf import setting
from ..source import compute_image_key, resolve_source_to_pil
from ..storage import get_manifest, get_storage, set_manifest, storage_assets_exist

logger = logging.getLogger(__name__)


class AssetManifestEntry(TypedDict, total=False):
    """A single entry in the generated asset manifest."""
    src: str
    url: str
    type: str
    sizes: str
    purpose: Optional[str]
    rel: Optional[str]
    media: Optional[str]
    name: Optional[str]
    meta_tag: Optional[str]
    html_tag: Optional[str]
    dark: Optional[bool]
    width: Optional[int]
    height: Optional[int]


@dataclass
class AssetTask:
    """A rendered image ready to be persisted into storage.

    Attributes:
        filename: Relative path for the file in the asset directory.
        content: Raw byte content of the image.
        mimetype: MIME type of the generated asset.
        metadata: Additional attributes (rel, sizes, purpose, etc.) for the manifest.
    """
    filename: str
    content: bytes
    mimetype: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def parse_color(color: Any) -> Optional[Tuple[int, int, int, int]]:
    """Parses a color value into an RGBA integer tuple.

    Supports hex strings, lists/tuples, and color names.

    Args:
        color: The input color which can be a hex string ('#fff'),
            an RGBA tuple/list, or a recognized color name.

    Returns:
        An (R, G, B, A) tuple or None if parsing fails.
    """
    if color is None:
        return None
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        if len(color) == 3:
            return (int(color[0]), int(color[1]), int(color[2]), 255)
        return (int(color[0]), int(color[1]), int(color[2]), int(color[3]))

    c = str(color).lstrip("#")
    if len(c) == 3:
        c = "".join([x * 2 for x in c])
    if len(c) == 6:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)
    if len(c) == 8:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16))
    return None


def render_canvas(
    logo: Image.Image,
    size: Tuple[int, int],
    bg_color: Tuple[int, int, int, int],
    padding: float = 0.0,
) -> Image.Image:
    """Renders a logo onto a canvas with a specified background color and padding.

    Args:
        logo: PIL Image instance (the source logo).
        size: Target (width, height) of the canvas.
        bg_color: Solid (R, G, B, A) background color.
        padding: Percentage of padding (0.0 to 1.0) around the logo.

    Returns:
        A new PIL Image centered and padded on the specified background.
    """
    canvas = Image.new("RGBA", size, bg_color)

    # Calculate logo target area with padding
    w, h = size
    target_w = int(w * (1.0 - padding * 2))
    target_h = int(h * (1.0 - padding * 2))

    # Resize logo maintaining aspect ratio
    logo_w, logo_h = logo.size
    ratio = min(target_w / logo_w, target_h / logo_h)
    new_w = int(logo_w * ratio)
    new_h = int(logo_h * ratio)

    # Use LANCZOS for high-quality downsampling
    resized_logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Calculate centered position
    offset = ((w - new_w) // 2, (h - new_h) // 2)

    # Paste using transparent mask if logo is RGBA
    mask = resized_logo if resized_logo.mode == "RGBA" else None
    canvas.paste(resized_logo, offset, mask)

    return canvas


def build_manifest_entry(
    task: AssetTask,
    url: str,
    src: str,
) -> AssetManifestEntry:
    """Constructs a standardized manifest entry dictionary from a generator task.

    Args:
        task: The completed AssetTask.
        url: Public URL of the saved asset.
        src: Relative storage path for the asset.

    Returns:
        A typed dictionary for inclusion in manifest.json.
    """
    entry: AssetManifestEntry = {
        "src": src,
        "url": url,
        "type": task.mimetype,
        **task.metadata
    }

    # Generate format-specific HTML boilerplate based on task metadata
    name = task.metadata.get("name")
    media = task.metadata.get("media")
    rel = task.metadata.get("rel")
    sizes = task.metadata.get("sizes", "any")

    if name:
        entry["meta_tag"] = f'<meta name="{name}" content="{url}">'

    if media:
        # Standard format for Apple startup images (splash screens)
        entry["html_tag"] = f'<link rel="apple-touch-startup-image" href="{url}" media="{media}">'
    elif rel:
        # Standard format for linked icons and favicons
        entry["html_tag"] = f'<link rel="{rel}" href="{url}" sizes="{sizes}">'

    # Allow task-specific overrides for HTML/Meta tags
    if "meta_tag" in task.metadata:
        entry["meta_tag"] = task.metadata["meta_tag"]
    if "html_tag" in task.metadata:
        entry["html_tag"] = task.metadata["html_tag"]

    print(f"DEBUG: build_manifest_entry for {task.filename}: {entry}")
    return entry


async def upload_asset(
    storage: Any,
    task: AssetTask,
    semaphore: asyncio.Semaphore,
) -> AssetManifestEntry:
    """Persists a single asset to storage and returns its final manifest entry.

    Args:
        storage: Django storage backend.
        task: The asset task containing filename and raw content.
        semaphore: Async concurrency governor.

    Returns:
        The completed manifest entry dictionary.
    """
    async with semaphore:
        def _save():
            # Overwrite if file already exists in case of partial runs or force updates
            if storage.exists(task.filename):
                storage.delete(task.filename)
            saved_name = storage.save(task.filename, ContentFile(task.content))
            return storage.url(saved_name), saved_name

        url, src = await sync_to_async(_save)()
        return build_manifest_entry(
            task, url, src
        )


async def get_or_generate_assets_async(
    img: Any,
    generator_fn: Callable[..., Generator[AssetTask, None, None]],
    **kwargs
) -> List[AssetManifestEntry]:
    """Primary entry point to orchestrate asset generation, caching, and storage.

    This function automatically handles:
    1. Input normalization and efficient cache key computation.
    2. Cached asset lookup from manifest.json.
    3. Parallel asset rendering and storage upload.
    4. Manifest persistence.

    Args:
        img: Source image (bytes, path, or PIL object).
        generator_fn: Generator yielding AssetTask objects.
        **kwargs: Additional generation settings (background, padding, etc.).

    Returns:
        A list of manifest entries for the generated or cached assets.
    """

    generator_name = generator_fn.__name__

    # 1. Compute deterministic cache key
    source_key = await sync_to_async(
        compute_image_key
    )(img, kwargs)

    if kwargs.get("asset_dir"):
        asset_dir = kwargs.pop("asset_dir")
    else:
        asset_dir = posixpath.join(setting("OUTPUT_PATH"), source_key)

    # 2. Cache Check (unless 'force' is True)
    if not kwargs.get("force", False):
        if await sync_to_async(storage_assets_exist)(asset_dir, generator_name):
            cached = await sync_to_async(get_manifest)(asset_dir, generator_name)
            if cached:
                logger.debug("PWA Cache: hit for %s:%s",
                             asset_dir, generator_name)
                return cached

    # 3. Generation Phase (CPU Intensive)
    logger.debug("PWA generation: starting for %s:%s",
                 asset_dir, generator_name)

    # 3.1. Normalize source to PIL
    source_img = await sync_to_async(resolve_source_to_pil)(img)

    # Offload generator execution to a separate thread as it is CPU bound
    def _run_generator():
        return list(generator_fn(source_img, asset_dir=asset_dir, **kwargs))

    tasks = await sync_to_async(_run_generator, thread_sensitive=False)()

    # 4. Storage Phase (Parallel Upload)
    max_concur = setting("MAX_CONCURRENT_UPLOADS")
    sem = asyncio.Semaphore(max_concur)
    storage = get_storage()
    upload_futures = [
        upload_asset(
            storage, task, sem
        )
        for task in tasks
    ]
    entries = await asyncio.gather(*upload_futures)

    # 5. Persist Manifest
    await sync_to_async(set_manifest)(asset_dir, entries, generator_name)
    logger.debug("PWA generation: complete for %s:%s",
                 asset_dir, generator_name)

    return entries
