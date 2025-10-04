# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Local Development
- `make serve` - Start the development environment using Docker (requires Docker Engine like OrbStack)
- `make shell` - Access Django shell with shell_plus and IPython
- `make bash` - Access container bash shell
- `make test` - Run pytest test suite
- `make manage "<command>"` - Run Django management commands (e.g., `make manage "collectstatic"`)

### Database & Migrations
- `make makemigrations` - Create new Django migrations
- `make manage "migrate"` - Apply database migrations

### Stripe Integration
- `make stripe-sync` - Sync Stripe products and prices to local database
- `make test-webhook` - Test Stripe webhook functionality

### Frontend Build
- `pnpm run build` - Production build of frontend assets
- `pnpm run start` - Development server for frontend assets
- `pnpm run watch` - Watch mode for frontend development

### Code Quality
- `poetry run ruff check` - Run Python linting
- `poetry run ruff format` - Format Python code
- `poetry run djlint --check .` - Check Django template formatting
- `poetry run pytest` - Run Python tests

## Architecture Overview

### Tech Stack
- **Backend**: Django 5.x with single-app architecture (`core` app)
- **Database**: PostgreSQL
- **Task Queue**: django-q2 for background tasks
- **Frontend**: Stimulus.js controllers + TailwindCSS
- **API**: django-ninja for REST APIs with Pydantic schemas
- **Authentication**: django-allauth with GitHub OAuth
- **Payments**: dj-stripe for Stripe integration
- **Logging**: structlog with logfire integration

### Project Structure
- `core/` - Main Django application containing all business logic
  - `models.py` - Django models with business logic (fat models pattern)
  - `views.py` - Django views (skinny views pattern)
  - `api/` - django-ninja API endpoints
  - `tasks.py` - Background tasks using django-q2
  - `agents/` - AI agent implementations using pydantic-ai
  - `management/commands/` - Custom Django management commands
- `frontend/` - Frontend assets and templates
  - `src/controllers/` - Stimulus.js controllers
  - `templates/` - Django templates
  - `webpack/` - Webpack configuration
- `tuxseo/` - Django project configuration
- `deployment/` - Docker deployment files

### Key Design Patterns

**Single App Architecture**: Everything lives in the `core` Django app to maintain simplicity and avoid over-engineering.

**Fat Models, Skinny Views**: Business logic is primarily in Django models and mixins, while views handle request/response only.

**Server-Side First**: Prefer Django templates and server-side rendering over complex client-side JavaScript solutions.

**Stimulus.js Integration**: Use Stimulus controllers for interactive frontend behavior, connecting via data attributes.

### Database Models
Key models include:
- `Project` - Main project entity with AI-generated analysis
- `GeneratedBlogPost` - AI-generated blog content
- `BlogPostTitleSuggestion` - AI-suggested blog titles
- `Competitor` - Competitor analysis data
- `Keyword` - SEO keyword tracking
- `Profile` - User profile and subscription status

### AI Integration
The application uses pydantic-ai for AI agent functionality:
- Content generation agents in `core/agents/`
- AI model configuration supports Anthropic, Gemini, and Perplexity
- Structured outputs using Pydantic schemas in `core/schemas.py`

### Background Tasks
Uses django-q2 for async task processing:
- Tasks defined in `core/tasks.py`
- Redis as the task broker
- Background processing for AI content generation

### Frontend Architecture
- **Stimulus.js**: Controllers in `frontend/src/controllers/` handle interactivity
- **TailwindCSS**: Utility-first CSS framework
- **Webpack**: Asset bundling with separate dev/prod configs
- **Bootstrap**: Component library for UI elements

### Environment Setup
1. Copy `.env.example` to `.env` and configure variables
2. Run `poetry install` to install Python dependencies
3. Run `make serve` to start development environment
4. Access application at `http://localhost:8009/`
5. First user becomes admin/superuser automatically

### Testing
- Uses Django's built-in testing framework with pytest
- Test files in `core/tests/`
- Run tests with `make test` or `poetry run pytest`
- Fixtures should be minimal, create test data in-context when possible
- Don't write or execute tests unless directly told to do so.
- Don't run pnpm commands.

### Key Conventions
- Follow PEP 8 for Python code style
- Use descriptive variable names with underscores
- Prefer Django's built-in features over external libraries
- Keep client-side JavaScript simple with Stimulus controllers
- Use semantic HTML elements (dialog, details/summary, etc.)
- Validate simple constraints in database, complex logic in Django models

### Dependencies Management
- Python dependencies managed with Poetry (`pyproject.toml`)
- Add new dependencies: `poetry add <package>`
- Export requirements: `poetry export -f requirements.txt --output requirements.txt --without-hashes`
- Frontend dependencies in `package.json`

### Deployment
- Docker-based deployment with separate containers for app and workers
- Uses CapRover for container orchestration
- Environment variables configured per environment
- GitHub Actions for CI/CD pipeline
