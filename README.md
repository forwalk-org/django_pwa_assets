# django-pwa-assets

Complete PWA asset generation for Django — inspired by [pwa-asset-generator](https://github.com/elegantapp/pwa-asset-generator).

Generates icons, favicons, Windows tiles, and iOS splash screens from a single source image. Configurable storage backend (local filesystem or S3/GCS/Azure), dark mode splash support, JPEG output, and a full override chain so every parameter can be set globally in `settings.py` or overridden per-call.

---

## Features

| Feature | Description |
|---|---|
| **Icons** | `any`, `maskable`, `monochrome` — full recommended size set |
| **Favicons** | `favicon.ico` (16+32px combined) + standalone PNGs |
| **Windows mstiles** | 70×70, 150×150, 310×310, 310×150 |
| **iOS splash screens** | 38 images covering iPhone SE → iPhone 16 Pro Max + all iPads |
| **Dark mode splashes** | Second set with `(prefers-color-scheme: dark)` — iOS 13+ |
| **JPEG output** | educes splash size by ~90% |
| **`opaque` flag** | Force solid white canvas for `any` icons|
| **Configurable storage** | Any Django `STORAGES` alias — local, S3, GCS, Azure, CDN |
| **Override chain** | `kwargs > PWA_ASSETS settings > defaults` |
| **Async-first** | Native async pipeline; sync wrappers (`get_or_generate_*`) for WSGI/scripts |
---

## Installation

```bash
pip install git+https://github.com/forwalk-org/django_pwa_assets.git

# Optional: SVG source support
pip install "django-pwa-assets[svg] @ git+https://github.com/forwalk-org/django_pwa_assets.git"
```

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "django_pwa_assets",
]
```

---

## Quickstart

With zero configuration, files land in `MEDIA_ROOT`:

```django
{% load pwa_assets %}
{% pwa_head_tags "/srv/media/logo.svg" %}
```

---

## Settings (`PWA_ASSETS`)

All settings are optional. Every parameter can also be overridden per-call.

```python
# settings.py
PWA_ASSETS = {
    # predefinite path do default site icon
    "DEFAULT_IMAGE": None,
    # Storage — any alias defined in STORAGES
    "STORAGE": "pwa_assets",

    # Sub-paths within the storage
    "OUTPUT_PATH":         "pwa/icons",      # icons

    # Icon generation
    "PURPOSES":             ("any", "maskable"),  # add "monochrome" if needed
    "INCLUDE_LEGACY_SIZES": False,
    "BACKGROUND_COLOR":     "#1F4E79",  # CSS hex, applies to all variants
    "PADDING_RATIO":        0.05,       # 5% padding around logo in "any"
    "MASKABLE_SAFE_AREA":   0.80,       # W3C safe zone (80% of canvas)
    "MONOCHROME_THRESHOLD": 128,
    "OPAQUE":               False,      # force opaque canvas for "any"

    # Output format (PNG or JPEG)
    "OUTPUT_FORMAT": "jpeg",  # strongly recommended for splash screens
    "JPEG_QUALITY":  80,

    # Splash screens
    "SPLASH_BACKGROUND_COLOR": "#1F4E79",  # falls back to BACKGROUND_COLOR
    "SPLASH_LOGO_RATIO":       0.25,       # logo = 25% of shorter dimension
    "SPLASH_PORTRAIT_ONLY":    False,
    "SPLASH_MIN_IOS":          None,       # e.g. "iOS 14"
    "SPLASH_DARK_BACKGROUND":  "#0A1628",  # enables dark mode splash set
}
```

### Dedicated storage for PWA assets

```python
STORAGES = {
    "default":    {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},

    # Dedicated PWA asset storage — separate from user media
    "pwa_assets": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name":   "my-pwa-assets",
            "location":      "pwa",
            "custom_domain": "cdn.example.com",  # CDN frontend
        },
    },
}

PWA_ASSETS = {"STORAGE": "pwa_assets"}
```

---

## Caching

`django-pwa-assets` uses a **two-tier manifest cache** to avoid redundant I/O on every request:

1. **Tier 1 — Django cache** (`CACHE_NAME`): in-memory / Redis / Memcached lookup. Nearly zero latency.
2. **Tier 2 — manifest JSON file** on the storage backend (e.g. `icons.json` next to the generated files). Always persisted; used as fallback when the cache is cold.

On every request the system checks Tier 1 first, falls back to Tier 2 (and back-fills Tier 1), and only regenerates assets when neither has a valid manifest.

### When to enable the Django cache

| Storage type | Recommendation |
|---|---|
| **Remote** (S3, GCS, Azure, CDN) | **Strongly recommended.** Every Tier-2 miss costs a network round-trip. Without a fast cache, each cold request will call the remote storage API. |
| **Local filesystem** | Optional. Tier 2 (disk read) is already cheap, so the cache gives only a marginal benefit. Leave `CACHE_NAME` unset here if you prefer simplicity. |

### Configuration

```python
# settings.py
PWA_ASSETS = {
    # Django cache alias to use for Tier 1.
    # Set to None (or omit) to skip the in-memory cache and rely on disk only.
    "CACHE_NAME": "pwa_cache",     # default: "default"
    "CACHE_TIMEOUT": 86400 * 365,    
}

# Add a dedicated cache entry in CACHES (optional but recommended):
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "pwa_cache": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://127.0.0.1:6379/1",
    },
}
```

To **disable** the Django cache entirely and rely only on the manifest JSON file on disk:

```python
PWA_ASSETS = {"CACHE_NAME": None}
```

---

## Template tags

```django
{% load pwa_assets %}
```

### `{% pwa_head_tags %}` — all assets in one call

```django
{% pwa_head_tags "/srv/media/logo.svg"
    background="#1F4E79"
    theme_color="#1F4E79"
    dark_background="#0A1628"
    portrait_only="true"
    min_ios="iOS 14"
    output_format="jpeg"
    with_favicons="true"
    with_mstiles="true" %}
```

### Individual tags

```django
{# Icon <link> tags #}
{% pwa_icons img_path
    purposes="any,maskable"
    background="#1F4E79"
    opaque="false"
    padding="0.05"
    theme_color="#1F4E79"
    include_legacy="false"
    output_format="png" %}

{# Manifest icon list (Python list for use in views) #}
{% pwa_icon_entries img_path as icon_list %}

{# Favicon tags: shortcut icon + PNG 16/32 #}
{% pwa_favicons img_path background="#1F4E79" %}

{# Windows mstile meta tags #}
{% pwa_mstiles img_path background="#1F4E79" tile_color="#1F4E79" %}

{# iOS splash screen tags (with optional dark mode) #}
{% pwa_splashes img_path
    background="#1F4E79"
    dark_background="#0A1628"
    logo_ratio="0.25"
    portrait_only="true"
    min_ios="iOS 14"
    output_format="jpeg"
    jpeg_quality="80" %}
```

All kwargs are optional — omitting falls through to `PWA_ASSETS` then defaults.

---



## Python API

All public symbols are accessible from the top-level package:

```python
from django_pwa_assets import (
    # Async entry points (ASGI / Django async views)
    aget_or_generate_all,
    aget_or_generate_icons,
    aget_or_generate_favicons,
    aget_or_generate_mstiles,
    aget_or_generate_splashes,
    # Sync entry points (WSGI / management commands)
    get_or_generate_all,
    get_or_generate_icons,
    get_or_generate_favicons,
    get_or_generate_mstiles,
    get_or_generate_splashes,
    # Generator functions (for custom pipelines)
    generate_icons,
    generate_favicons,
    generate_mstiles,
    generate_splashes,
    # Data types
    AssetManifestEntry,
    AssetTask,
    AllAssets,
)
```

### Async usage (ASGI views, async management commands)

```python
from django_pwa_assets import aget_or_generate_all, aget_or_generate_icons

# Generate all asset categories
assets: dict = await aget_or_generate_all(
    "logo.svg",
    background="#1F4E79",
    with_favicons=True,
    with_splashes=True,
    with_mstiles=False,
)
assets["icons"]    # list[AssetManifestEntry]
assets["favicons"] # list[AssetManifestEntry]
assets["splashes"] # list[AssetManifestEntry]

# Generate only icons
icons = await aget_or_generate_icons(
    "logo.svg",
    background="#1F4E79",
    purposes=("any", "maskable"),
)
```

### Sync usage (WSGI views, scripts)

```python
from django_pwa_assets import get_or_generate_all, get_or_generate_splashes

assets = get_or_generate_all("logo.svg", background="#1F4E79")

splashes = get_or_generate_splashes(
    "logo.svg",
    background="#1F4E79",
    dark_background="#0A1628",
    portrait_only=True,
    min_ios="iOS 14",
    output_format="jpeg",
    jpeg_quality=80,
)
```

### Web App Manifest integration

```python
from django.http import JsonResponse
from django_pwa_assets import get_or_generate_icons

def manifest_view(request):
    icons = get_or_generate_icons(request.session.get("logo_path", "logo.svg"))
    return JsonResponse({
        "name": "My App",
        "icons": icons,  # list[AssetManifestEntry]
    })
```

---

## Dark mode splash screens

When `SPLASH_DARK_BACKGROUND` is set (or `dark_background` tag kwarg), the
package generates **two sets** of splash screens:

- Light set: normal filenames, normal media queries
- Dark set: `-dark` filename suffix, `(prefers-color-scheme: dark)` appended
  to each media query

iOS 13+ automatically picks the correct image based on the system setting.
No JavaScript required.

Example HTML output:

```html
<link rel="apple-touch-startup-image"
      media="(device-width: 393px) and (device-height: 852px) and (-webkit-device-pixel-ratio: 3) and (orientation: portrait)"
      href="/pwa/splashes/splash-1179x2556-portrait.jpg">

<link rel="apple-touch-startup-image"
      media="(device-width: 393px) and (device-height: 852px) and (-webkit-device-pixel-ratio: 3) and (orientation: portrait) and (prefers-color-scheme: dark)"
      href="/pwa/splashes/splash-1179x2556-portrait-dark.jpg">
```

---

## JPEG for splash screens

PNG splash screens for modern iPhones can exceed **3 MB** each (38 images = ~100 MB total).
JPEG at quality 80 reduces each to **under 200 KB** with no visible difference on
a solid-colour background.

```python
PWA_ASSETS = {
    "OUTPUT_FORMAT": "jpeg",
    "JPEG_QUALITY":  80,
}
```

---

## Deploy checklist

```bash
# 1. Generate icons (runs once at deploy)
python manage.py generate_pwa_icons logo.svg

# 2. Generate splash screens (JPEG recommended)
python manage.py generate_pwa_splashes logo.svg --format jpeg

# 3. Add tags to base template
#    {% load pwa_assets %}
#    {% pwa_head_tags logo_path %}

# 4. Add icons to manifest view
#    from django_pwa_assets.templatetags.pwa_assets import pwa_icon_entries
#    icons = pwa_icon_entries(logo_path)
```

---

## Updating splash screen specs

The splash screen dimensions live in `generators/splashes.py` (`SPLASH_SCREENS` tuple).
When Apple releases new devices, add a new entry to `_IOS_RAW_DEVICES` — everything
else updates automatically.

`SPEC_VERSION = "2025.06"` in `source.py` tracks the last spec update and
automatically busts the asset cache when incremented.

> **Package version**: `0.2.0`

---

## License

MIT
