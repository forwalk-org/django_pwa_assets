from unittest import mock
from django.test import TestCase
from django.template import Context, Template
from django_pwa_assets.generators.base import AssetManifestEntry

# Mock functions to avoid real image generation and async issues
def mock_get_or_generate_icons(*args, **kwargs):
    return [
        {
            "src": "/media/pwa/any-192x192.png",
            "url": "http://example.com/media/pwa/any-192x192.png",
            "type": "image/png",
            "purpose": "any",
            "sizes": "192x192",
            "rel": "icon"
        }
    ]

def mock_get_or_generate_favicons(*args, **kwargs):
    return [
        {
            "src": "/media/pwa/favicon.ico",
            "url": "http://example.com/media/pwa/favicon.ico",
            "type": "image/x-icon",
            "purpose": "favicon",
            "sizes": "any",
            "rel": "icon"
        }
    ]

def mock_get_or_generate_splashes(*args, **kwargs):
    return [
        {
            "src": "/media/pwa/splash-1125x2436.png",
            "url": "http://example.com/media/pwa/splash-1125x2436.png",
            "type": "image/png",
            "purpose": "splash",
            "media": "(device-width: 375px)"
        }
    ]

def mock_get_or_generate_mstiles(*args, **kwargs):
    return [
        {
            "src": "/media/pwa/mstile-150x150.png",
            "url": "http://example.com/media/pwa/mstile-150x150.png",
            "type": "image/png",
            "purpose": "mstile",
            "name": "msapplication-square150x150logo"
        }
    ]

def mock_get_or_generate_all(*args, **kwargs):
    return {
        "icons": [
            {
                "src": "/media/pwa/any-192x192.png",
                "url": "http://example.com/media/pwa/any-192x192.png",
                "type": "image/png",
                "purpose": "any",
                "sizes": "192x192",
                "rel": "icon"
            }
        ],
        "favicons": [],
        "splashes": [],
        "mstiles": []
    }

class TemplateTagsTest(TestCase):
    def render_template(self, string, context=None):
        context = context or {}
        return Template(string).render(Context(context))

    @mock.patch('django_pwa_assets.templatetags.pwa_assets.get_or_generate_icons', side_effect=mock_get_or_generate_icons)
    def test_pwa_icons_tag(self, mock_icons):
        html = self.render_template("{% load pwa_assets %}\n{% pwa_icons 'logo.png' %}")
        self.assertIn('<link rel="icon"', html)
        self.assertIn('href="/media/pwa/any-192x192.png"', html)
        self.assertIn('sizes="192x192"', html)

    @mock.patch('django_pwa_assets.templatetags.pwa_assets.get_or_generate_icons', side_effect=mock_get_or_generate_icons)
    def test_pwa_icon_entries_tag(self, mock_icons):
        html = self.render_template("{% load pwa_assets %}\n{% pwa_icon_entries 'logo.png' as entries %}{{ entries|length }}")
        self.assertEqual(html.strip(), "1")

    @mock.patch('django_pwa_assets.templatetags.pwa_assets.get_or_generate_splashes', side_effect=mock_get_or_generate_splashes)
    def test_pwa_splashes_tag(self, mock_splashes):
        html = self.render_template("{% load pwa_assets %}\n{% pwa_splashes 'logo.png' %}")
        self.assertIn('<link rel="apple-touch-startup-image"', html)
        self.assertIn('href="/media/pwa/splash-1125x2436.png"', html)
        self.assertIn('media="(device-width: 375px)"', html)

    @mock.patch('django_pwa_assets.templatetags.pwa_assets.get_or_generate_favicons', side_effect=mock_get_or_generate_favicons)
    def test_pwa_favicons_tag(self, mock_favicons):
        html = self.render_template("{% load pwa_assets %}\n{% pwa_favicons 'logo.png' %}")
        self.assertIn('<link rel="shortcut icon"', html)
        self.assertIn('href="/media/pwa/favicon.ico"', html)

    @mock.patch('django_pwa_assets.templatetags.pwa_assets.get_or_generate_mstiles', side_effect=mock_get_or_generate_mstiles)
    def test_pwa_mstiles_tag(self, mock_mstiles):
        html = self.render_template("{% load pwa_assets %}\n{% pwa_mstiles 'logo.png' tile_color='#ffffff' %}")
        self.assertIn('<meta name="msapplication-square150x150logo"', html)
        self.assertIn('content="/media/pwa/mstile-150x150.png"', html)
        self.assertIn('<meta name="msapplication-TileColor" content="#ffffff"', html)

    @mock.patch('django_pwa_assets.templatetags.pwa_assets.get_or_generate_all', side_effect=mock_get_or_generate_all)
    def test_pwa_head_tags(self, mock_all):
        html = self.render_template("{% load pwa_assets %}\n{% pwa_head_tags 'logo.png' %}")
        self.assertIn('<link rel="icon"', html)
        self.assertIn('href="/media/pwa/any-192x192.png"', html)
        self.assertIn('sizes="192x192"', html)

    def test_missing_img(self):
        with self.settings(PWA_ASSETS={'DEFAULT_IMAGE': None}):
            html = self.render_template("{% load pwa_assets %}\n{% pwa_icons %}")
            self.assertIn('<!-- pwa_icons: img required -->', html)
            
            html = self.render_template("{% load pwa_assets %}\n{% pwa_head_tags %}")
            self.assertEqual(html.strip(), "")
