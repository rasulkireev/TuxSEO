"""
Django App Configuration for SEO Content Validator
"""

from django.apps import AppConfig


class SrcConfig(AppConfig):
    """App configuration for SEO Content Validator"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'src'
    verbose_name = 'SEO Content Validator'

    def ready(self):
        """
        Perform initialization when app is ready.
        Import signals, register tasks, etc.
        """
        # Import signals if you have any
        # from . import signals
        pass
