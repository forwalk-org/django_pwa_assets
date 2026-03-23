"""Image source resolution and identity for PWA assets.

This module provides a unified API to:
1. Resolve various input types (Paths, Bytes, PIL images) to raw bytes.
2. Compute a unique identity key for a source + generation parameters.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import posixpath
from pathlib import Path
from typing import Any, Dict, Final, Optional, Tuple, Union

from PIL import Image
from django.contrib.staticfiles import finders
from django.core.files.base import ContentFile, File
from django.core.files.storage import default_storage

from .conf import setting
from .storage import get_storage

# Optional dependencies for SVG handling and fast hashing
try:
    import cairosvg
except ImportError:
    cairosvg = None

try:
    from scour import scour
except ImportError:
    scour = None

try:
    import blake3
except ImportError:
    blake3 = None


# Bump this string whenever default sizes or specs change to bust the cache.
SPEC_VERSION: str = "2025.06"

# Separator between identity components used in raw key strings.
_SEP: Final[str] = "||"

# Keys in gen_params that do not affect the visual output of the rendered asset.
IGNORED_PARAM_KEYS: Final[frozenset] = frozenset(
    {"force", "output_path", "storage"}
)


def read_path(path: Union[str, Path], storage: Any = None) -> Tuple[bytes, str]:
    """Reads a file from Django static files or configured storage.

    Args:
        path: The path or string representing the resource location.
        storage: Optional storage backend; defaults to the configured project storage.

    Returns:
        A tuple containing the raw file bytes and the lowercase file extension.

    Raises:
        ValueError: If the file is not found in static finders or storage.
    """
    st = storage or get_storage()
    path_str = str(path)

    # 1. Search in Django static files
    static_path = finders.find(path_str)
    if static_path:
        p = Path(static_path)
        return p.read_bytes(), p.suffix.lower()

    # 2. Search in configured storage
    if st.exists(path_str):
        with st.open(path_str) as fh:
            return fh.read(), Path(path_str).suffix.lower()

    raise ValueError(
        f"PWA: Source path '{path}' not found in static files or "
        "configured storage."
    )


def resolve_source_to_bytes(img: Any, storage: Any = None) -> Tuple[bytes, str]:
    """Normalizes any supported input type into raw bytes and a file extension.

    Args:
        img: The source image (bytes, Path, file-like, or PIL Image).
        storage: Optional storage backend for path resolution.

    Returns:
        A tuple of (raw_bytes, extension).

    Raises:
        ValueError: If the input type is not supported.
    """
    if isinstance(img, (bytes, bytearray)):
        return bytes(img), ""

    if isinstance(img, (str, Path)):
        return read_path(img, storage=storage)

    if hasattr(img, "read"):
        name = getattr(img, "name", "")
        ext = Path(name).suffix.lower() if name else ""
        return img.read(), ext

    if isinstance(img, Image.Image):
        # Convert PIL Image directly to PNG bytes
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), ".png"

    raise ValueError(f"PWA: Unsupported source type '{type(img).__name__}'.")


def resolve_source_to_pil(img: Any, storage: Any = None) -> Image.Image:
    """Normalizes any supported input type into a RGBA PIL Image object.

    Handles SVG/SVGZ detection and rasterization automatically.

    Args:
        img: The source image input.
        storage: Optional storage backend.

    Returns:
        A PIL Image in RGBA mode.
    """
    if isinstance(img, Image.Image):
        pil_img = img.convert("RGBA")
        # Ensure it has the svg_source attribute even if already a PIL Image
        if not hasattr(pil_img, "svg_source"):
            setattr(pil_img, "svg_source", None)
        return pil_img

    raw_bytes, ext = resolve_source_to_bytes(img, storage=storage)

    # Auto-detect SVG/SVGZ content
    if is_svg(raw_bytes) or ext == ".svg":
        if setting('CLEAN_IMAGE_SVG'):
            svg = optimize_svg(raw_bytes)
        else:
            svg = raw_bytes
        pil_img = svg_to_pil(svg)
        # Store SVG bytes on the object for later use (e.g. copying)
        print("b"*20)
        print(svg)
        print("aaa")
        setattr(pil_img, "svg_source", svg)
        return pil_img

    # Native image fallback
    pil_img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    setattr(pil_img, "svg_source", None)
    return pil_img


def is_svg(data: bytes) -> bool:
    """Detects if the provided bytes represent an SVG or SVGZ file.

    Args:
        data: The byte string to inspect.

    Returns:
        True if SVG content is detected, False otherwise.
    """
    if not data:
        return False

    # Detect GZIP header for SVGZ
    if data.startswith(b"\x1f\x8b"):
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
                header = f.read(128)
                return b"<svg" in header or b"<?xml" in header
        except Exception:
            return False

    # Check first 512 bytes for standard SVG/XML markers
    sample = data[:512].lower()
    return b"<svg" in sample or b"<?xml" in sample


def optimize_svg(data: bytes) -> bytes:
    """Optimizes SVG data using the Scour library if available.

    Handles decompressing and re-compressing SVGZ transparently.

    Args:
        data: Raw SVG or SVGZ bytes.

    Returns:
        Optimized bytes (compressed if input was compressed).
    """
    if scour is None:
        raise ImportError("scour must be installed to optimize SVG files.")

    try:
        is_compressed = data.startswith(b"\x1f\x8b")
        content = data
        if is_compressed:
            content = gzip.decompress(data)

        # Configure Scour options for a balance of safety and size
        options = scour.sanitizeOptions()
        options.quiet = True
        options.strip_ids = True

        optimized = scour.scourString(
            content.decode("utf-8", errors="ignore"), options=options
        )
        optimized_bytes = optimized.encode("utf-8")

        return gzip.compress(optimized_bytes) if is_compressed else optimized_bytes
    except Exception as e:
        if setting('RAISE_ON_CLEAN_IMAGE_SVG_ERROR'):
            raise ValueError(f"PWA: Failed to optimize SVG: {e}") from e
        # Fallback to original on any scouring error
        return data


def svg_to_pil(data: bytes, size: Optional[Tuple[int, int]] = None) -> Image.Image:
    """Rasterizes SVG data into a PIL Image using CairoSVG.

    Args:
        data: Raw SVG or SVGZ bytes.
        size: Target dimensions as (width, height); defaults to (512, 512).

    Returns:
        A PIL Image in RGBA mode.

    Raises:
        ImportError: If CairoSVG is not installed.
    """
    if cairosvg is None:
        raise ImportError(
            "PWA: SVG support requires 'cairosvg'. Install with 'pip install cairosvg'."
        )

    w, h = size or (512, 512)

    # Decompress SVGZ for CairoSVG if necessary
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)

    png_data = cairosvg.svg2png(
        bytestring=data, output_width=w, output_height=h)
    return Image.open(io.BytesIO(png_data)).convert("RGBA")


def serialize_params(gen_params: Dict[str, Any]) -> str:
    """Serializes generation parameters into a stable, deterministic JSON string.

    Args:
        gen_params: Dictionary of asset generation parameters.

    Returns:
        A compact JSON string with sorted keys.
    """
    relevant = {}
    for k, v in gen_params.items():
        if k in IGNORED_PARAM_KEYS:
            continue
        # Ensure lists/tuples are sorted for consistent hashing
        if isinstance(v, (list, tuple)):
            try:
                relevant[k] = sorted(v)
            except TypeError:
                relevant[k] = list(v)
        else:
            relevant[k] = v
    return json.dumps(relevant, sort_keys=True)


def get_hasher():
    """Returns a stable hexdigest function using blake3 or MD5."""
    if blake3 is not None:
        return lambda data: blake3.blake3(data).hexdigest()
    return lambda data: hashlib.md5(data).hexdigest()


def compute_image_key(
    img: Any,
    gen_params: Dict[str, Any]
) -> str:
    """Computes a unique cache key and its components for PWA assets.

    Args:
        img: The source image resource.
        gen_params: Dictionary of generation options.

    Returns:
        image key.
    """
    hexdigest = get_hasher()
    storage = getattr(img, "storage", None)

    # 1. Prefix: storage class name or object type name
    prefix = storage.__class__.__name__ if storage is not None else type(
        img).__name__

    # 2. Source Identity: stable identifier for the raw resource
    if isinstance(img, (str, Path)):
        identifier = str(img)
    elif isinstance(img, File):
        identifier = getattr(img, "name", "")
    elif isinstance(img, (ContentFile, io.BytesIO)):
        content = img.getvalue() if hasattr(img, "getvalue") else img.read()
        identifier = f"inmem:{hexdigest(content)}"
    elif isinstance(img, Image.Image):
        raw = img.tobytes()
        identifier = f"pil:{img.size}:{img.mode}:{hexdigest(raw)}"
    elif isinstance(img, (bytes, bytearray)):
        identifier = f"bytes:{hexdigest(bytes(img))}"
    else:
        identifier = str(img)

    options_str = serialize_params(gen_params)
    raw_key = f"{SPEC_VERSION}|{prefix}|{identifier}|{options_str}"
    image_key = hexdigest(raw_key.encode("utf-8"))[:12]

    return image_key
