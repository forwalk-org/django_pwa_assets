"""Django application configuration for django_pwa_assets.

This module registers ``django_pwa_assets`` with Django's application
registry so that template tags and management commands are auto-discovered.
"""

from django.apps import AppConfig


class DjangoPwaAssetsConfig(AppConfig):
    """AppConfig for the django_pwa_assets package.

    Attributes:
        name: Dotted Python module path used by Django's app registry.
    """

    name = "django_pwa_assets"
