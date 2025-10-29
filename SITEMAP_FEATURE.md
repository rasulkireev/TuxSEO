# Sitemap Feature Implementation

This document describes the sitemap link feature that allows users to add a sitemap URL to their project settings, automatically parse it, and analyze the pages for better content insertion in articles.

## Overview

Users can now add a sitemap URL to their project settings. When added:
1. The sitemap is immediately parsed to extract all URLs
2. Pages are analyzed in batches of 10 at a time
3. Each page is fetched and summarized using AI
4. A daily scheduled task checks for any unanalyzed pages and processes the next 10

## Database Schema

### Project Model
- Added `sitemap_url` field (URLField, max_length=500, blank=True)

### SitemapPage Model (New)
A new model to track pages discovered from the sitemap:

```python
class SitemapPage(BaseModel):
    project = ForeignKey(Project)
    url = URLField(max_length=500)
    
    # Content from Jina Reader
    date_scraped = DateTimeField(null=True)
    title = CharField(max_length=500)
    description = TextField()
    markdown_content = TextField()
    
    # AI Content
    date_analyzed = DateTimeField(null=True)
    summary = TextField()  # 2-3 sentence summary
```

## API Endpoints

### Update Sitemap URL
**POST** `/api/projects/update-sitemap-url`

Request body:
```json
{
  "project_id": 123,
  "sitemap_url": "https://example.com/sitemap.xml"
}
```

Response:
```json
{
  "status": "success",
  "message": "Sitemap URL updated successfully. Pages will be analyzed in batches of 10."
}
```

### Get User Settings
**GET** `/api/user/settings?project_id=123`

Now includes `sitemap_url` in the response:
```json
{
  "profile": { ... },
  "project": {
    "name": "Project Name",
    "url": "https://example.com",
    "sitemap_url": "https://example.com/sitemap.xml",
    "has_auto_submission_setting": false
  }
}
```

## Background Tasks

### parse_sitemap_and_save_urls(project_id)
- Triggered automatically when a sitemap URL is added/updated (via Django signal)
- Parses the sitemap XML (supports both regular sitemaps and sitemap indexes)
- Extracts all URLs and saves them as SitemapPage records
- Schedules the first batch of 10 pages for analysis

### analyze_sitemap_pages(project_id, limit=10)
- Analyzes up to 10 unanalyzed pages at a time
- For each page:
  - Fetches content using Jina Reader API
  - Generates a 2-3 sentence summary using AI (gemini-2.5-flash)
  - Saves the summary and marks the page as analyzed
- Can be called multiple times to process pages in batches

### analyze_project_sitemap_pages_daily()
- Scheduled to run every 24 hours
- Checks all projects with sitemap URLs
- For each project with unanalyzed pages, schedules another batch of 10 for analysis
- This ensures all sitemap pages are eventually analyzed

## Content Generation Integration

When generating blog posts, the system now includes both:
1. Manually added project pages (from the existing ProjectPage model)
2. Analyzed sitemap pages (from the new SitemapPage model)

The AI agent receives all these pages as context and can intelligently insert relevant links into the generated content.

## AI Agents

### summarize_page_agent (New)
- Model: `google-gla:gemini-2.5-flash`
- Input: WebPageContent (title, description, markdown_content)
- Output: String (2-3 sentence summary)
- Purpose: Creates concise summaries of sitemap pages for use in content generation

## Scheduled Tasks Configuration

Added to `Q_CLUSTER` in settings.py:

```python
"schedule": [
    {
        "func": "core.tasks.analyze_project_sitemap_pages_daily",
        "schedule_type": "I",
        "minutes": 1440,  # Run every 24 hours
        "name": "Analyze Project Sitemap Pages Daily",
    },
    # ... other scheduled tasks
]
```

## Django Signals

### parse_sitemap_on_save
- Triggered on `post_save` of Project model
- Checks if `sitemap_url` was added or changed
- Schedules `parse_sitemap_and_save_urls` task
- Uses `update_fields` to avoid unnecessary triggering

## Migration

**Migration**: `0033_add_sitemap_support.py`

Creates:
- `Project.sitemap_url` field
- `SitemapPage` model with unique constraint on (project, url)

## Admin Interface

The `SitemapPage` model is registered in the Django admin for easy viewing and management.

## Usage Flow

1. **User adds sitemap URL** via API endpoint or admin
2. **Immediate parsing**: Signal triggers sitemap parsing task
3. **Batch processing**: First 10 pages are analyzed immediately
4. **Daily checks**: Scheduled task processes next 10 pages daily until all are analyzed
5. **Content generation**: Analyzed pages are available as context for blog post generation

## Limitations

- Pages are processed in batches of 10 to avoid overwhelming the system
- Only pages that can be successfully fetched by Jina Reader are analyzed
- Failed pages are logged but not retried automatically
- Daily task ensures eventual analysis but may take time for large sitemaps

## Benefits

1. **Automatic discovery**: No need to manually add internal links
2. **Better content**: AI has more context about the project's pages
3. **Scalable**: Batch processing prevents resource exhaustion
4. **Maintainable**: Daily checks ensure new sitemap pages are discovered
5. **Smart linking**: AI can insert relevant internal links in generated articles

## Future Enhancements

Potential improvements:
- Configurable batch size per project
- Manual trigger for re-analyzing pages
- Priority system for important pages
- Sitemap change detection and re-parsing
- Analytics on which pages are most linked in articles
