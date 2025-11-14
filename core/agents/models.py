from django.db import models


class AIModel(models.TextChoices):
    GEMINI_FLASH = "google-gla:gemini-2.5-flash", "Gemini 2.5 Flash"
    PERPLEXITY_SONAR = "sonar", "Perplexity Sonar"


DEFAULT_AI_MODEL = AIModel.GEMINI_FLASH


def get_default_ai_model() -> str:
    """Returns the default AI model to use across the application."""
    return DEFAULT_AI_MODEL
