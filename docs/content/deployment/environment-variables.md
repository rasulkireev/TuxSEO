---
title: Environment Variables
description: Complete guide to configuring TuxSEO environment variables.
keywords: TuxSEO, environment variables, configuration, API keys
author: Rasul Kireev
---

This guide covers all environment variables needed to configure TuxSEO.

## Required variables

These variables are essential for TuxSEO to function:

### AI API Keys

TuxSEO uses several AI services to generate content and analyze your website. You need API keys for each service:

**OPENAI_API_KEY**
- Get your key from [OpenAI Platform](https://platform.openai.com/api-keys)
- Used for blog post content generation via GPT-Researcher
- Paid service with usage-based pricing

**TAVILY_API_KEY**
- Get your key from [Tavily](https://tavily.com/)
- Used by GPT-Researcher for web research and content generation
- Free tier available with 1,000 requests per month

**GEMINI_API_KEY**
- Get your key from [Google AI Studio](https://makersuite.google.com/app/apikey)
- Used for content generation and analysis
- Free tier available with generous limits

**PERPLEXITY_API_KEY**
- Get your key from [Perplexity](https://www.perplexity.ai/)
- Used for research and content enhancement
- Paid service with usage-based pricing

**JINA_READER_API_KEY**
- Get your key from [Jina AI](https://jina.ai/)
- Used for reading and processing web content
- Free tier available

**KEYWORDS_EVERYWHERE_API_KEY**
- Get your key from [Keywords Everywhere](https://keywordseverywhere.com/)
- Used for keyword research and analysis
- Paid service with credit-based pricing

### Database configuration

**POSTGRES_PASSWORD**
- Password for your PostgreSQL database
- Use a strong, randomly generated password
- Generate one with: `openssl rand -base64 32`

**REDIS_PASSWORD**
- Password for your Redis instance
- Use a strong, randomly generated password
- Generate one with: `openssl rand -base64 32`

### Django settings

**SECRET_KEY**
- Secret key for Django security features
- Must be kept confidential in production
- Generate one with: `python -c "import secrets; print(secrets.token_urlsafe(50))"`

**ALLOWED_HOSTS**
- Comma-separated list of domains that can access your application
- Example: `yourdomain.com,www.yourdomain.com`
- Use `*` for testing only (not secure for production)

**DEBUG**
- Set to `False` in production
- Set to `True` only for local development
- Never deploy to production with DEBUG=True

## Optional variables

These variables enhance functionality but aren't required:

### Email configuration

Configure these to send emails from TuxSEO (for notifications, password resets, etc.):

**EMAIL_HOST**
- SMTP server hostname
- Example: `smtp.gmail.com`

**EMAIL_PORT**
- SMTP server port
- Common values: `587` (TLS) or `465` (SSL)

**EMAIL_HOST_USER**
- Your email address for SMTP authentication

**EMAIL_HOST_PASSWORD**
- Password or app-specific password for your email account

**EMAIL_USE_TLS**
- Set to `True` if using TLS (port 587)
- Set to `False` if using SSL (port 465)

**DEFAULT_FROM_EMAIL**
- Email address shown as sender
- Example: `noreply@yourdomain.com`

### Storage configuration

Configure these to use cloud storage for media files:

**USE_S3**
- Set to `True` to enable AWS S3 storage
- Set to `False` to use local file storage

**AWS_ACCESS_KEY_ID**
- Your AWS access key ID
- Required if USE_S3 is True

**AWS_SECRET_ACCESS_KEY**
- Your AWS secret access key
- Required if USE_S3 is True

**AWS_STORAGE_BUCKET_NAME**
- Name of your S3 bucket
- Required if USE_S3 is True

**AWS_S3_REGION_NAME**
- AWS region for your S3 bucket
- Example: `us-east-1`

### Additional settings

**SITE_URL**
- Full URL where your TuxSEO instance is accessible
- Example: `https://yourdomain.com`
- Used for generating absolute URLs in emails and notifications

**DATABASE_URL**
- Complete PostgreSQL connection string
- Example: `postgresql://user:password@localhost:5432/dbname`
- Usually auto-configured in containerized deployments

**REDIS_URL**
- Complete Redis connection string
- Example: `redis://:password@localhost:6379/0`
- Usually auto-configured in containerized deployments

## Getting the .env.example file

The complete `.env.example` file with all variables and detailed comments is available in the TuxSEO repository.

Download it directly:

```bash
wget https://raw.githubusercontent.com/rasulkireev/tuxseo/main/.env.example -O .env
```

Or with curl:

```bash
curl -o .env https://raw.githubusercontent.com/rasulkireev/tuxseo/main/.env.example
```

This file includes all available options with explanations and example values.

## Security best practices

Follow these guidelines to keep your TuxSEO installation secure:

**Never commit .env files**
- Add `.env` to your `.gitignore`
- Use environment variables or secret management systems for production

**Use strong passwords**
- Generate random passwords for database and Redis
- Use at least 32 characters for production passwords

**Keep secrets confidential**
- Don't share your SECRET_KEY or API keys
- Rotate keys immediately if exposed

**Use HTTPS in production**
- Set ALLOWED_HOSTS to specific domains only
- Configure SSL/TLS certificates for your domain
- Never set DEBUG=True in production

**Limit access**
- Use firewall rules to restrict database and Redis access
- Only expose necessary ports to the internet
- Use strong authentication for all services
