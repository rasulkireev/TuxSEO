from django.db import models


class ContentType(models.TextChoices):
    SHARING = "SHARING", "Sharing"
    SEO = "SEO", "SEO"
    VS_COMPETITOR = "VS_COMPETITOR", "Vs. Competitor"


class Category(models.TextChoices):
    GENERAL_AUDIENCE = "General Audience", "General Audience"
    NICH_AUDIENCE = "Niche Audience", "Niche Audience"
    INDUSTRY_COMPANY = "Industry/Company", "Industry/Company"


class ProjectType(models.TextChoices):
    SAAS = "SaaS", "SaaS"
    HOSPITALITY = "Hospitality", "Hospitality"
    JOB_BOARD = "Job Board", "Job Board"
    LEGAL_SERVICES = "Legal Services", "Legal Services"
    MARKETING = "Marketing", "Marketing"
    NEWS_AND_MAGAZINE = "News and Magazine", "News and Magazine"
    ONLINE_TOOLS = "Online Tools, Utilities", "Online Tools, Utilities"
    ECOMMERCE = "Ecommerce", "Ecommerce"
    EDUCATIONAL = "Educational", "Educational"
    ENTERTAINMENT = "Entertainment", "Entertainment"
    FINANCIAL_SERVICES = "Financial Services", "Financial Services"
    HEALTH_AND_WELLNESS = "Health & Wellness", "Health & Wellness"
    PERSONAL_BLOG = "Personal Blog", "Personal Blog"
    REAL_ESTATE = "Real Estate", "Real Estate"
    SPORTS = "Sports", "Sports"
    TRAVEL_AND_TOURISM = "Travel and Tourism", "Travel and Tourism"
    OTHER = "Other"


class ProjectPageType(models.TextChoices):
    BLOG = "Blog", "Blog"
    ABOUT = "About", "About"
    CONTACT = "Contact", "Contact"
    FAQ = "FAQ", "FAQ"
    TERMS_OF_SERVICE = "Terms of Service", "Terms of Service"
    PRIVACY_POLICY = "Privacy Policy", "Privacy Policy"
    PRICING = "Pricing", "Pricing"
    OTHER = "Other", "Other"


class Language(models.TextChoices):
    ENGLISH = "English", "English"
    SPANISH = "Spanish", "Spanish"
    FRENCH = "French", "French"
    GERMAN = "German", "German"
    ITALIAN = "Italian", "Italian"
    PORTUGUESE = "Portuguese", "Portuguese"
    RUSSIAN = "Russian", "Russian"
    JAPANESE = "Japanese", "Japanese"
    CANTONESE = "Cantonese", "Cantonese"
    MANDARIN = "Mandarin", "Mandarin"
    ARABIC = "Arabic", "Arabic"
    KOREAN = "Korean", "Korean"
    HINDI = "Hindi", "Hindi"
    UKRAINIAN = "Ukrainian", "Ukrainian"
    # Add other languages as needed


class ProjectStyle(models.TextChoices):
    DIGITAL_ART = "Digital Art", "Digital Art"
    PHOTOREALISTIC = "Photorealistic", "Photorealistic"
    HYPER_REALISTIC = "Hyper-realistic", "Hyper-realistic"
    OIL_PAINTING = "Oil Painting", "Oil Painting"
    WATERCOLOR = "Watercolor", "Watercolor"
    CARTOON = "Cartoon", "Cartoon"
    ANIME = "Anime", "Anime"
    THREE_D_RENDER = "3D Render", "3D Render"
    SKETCH = "Sketch", "Sketch"
    POP_ART = "Pop Art", "Pop Art"
    MINIMALIST = "Minimalist", "Minimalist"
    SURREALIST = "Surrealist", "Surrealist"
    IMPRESSIONIST = "Impressionist", "Impressionist"
    PIXEL_ART = "Pixel Art", "Pixel Art"
    CONCEPT_ART = "Concept Art", "Concept Art"
    ISOMETRIC = "Isometric", "Isometric"
    LOW_POLY = "Low Poly", "Low Poly"
    RETRO = "Retro", "Retro"
    CYBERPUNK = "Cyberpunk", "Cyberpunk"
    STEAMPUNK = "Steampunk", "Steampunk"


class ProfileStates(models.TextChoices):
    STRANGER = "stranger"
    SIGNED_UP = "signed_up"
    SUBSCRIBED = "subscribed"
    CANCELLED = "cancelled"
    CHURNED = "churned"
    ACCOUNT_DELETED = "account_deleted"


class KeywordDataSource(models.TextChoices):
    GOOGLE_KEYWORD_PLANNER = "gkp", "Google Keyword Planner"
    CLICKSTREAM = "cli", "Clickstream"


class BlogPostStatus(models.TextChoices):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"


class ProjectPageSource(models.TextChoices):
    AI = "AI", "AI"
    SITEMAP = "SITEMAP", "Sitemap"
