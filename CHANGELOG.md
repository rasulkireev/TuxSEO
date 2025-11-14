<!-- Types of changes -->
**Added** for new features.
**Changed** for changes in existing functionality.
**Deprecated** for soon-to-be removed features.
**Removed** for now removed features.
**Fixed** for any bug fixes.
**Security** in case of vulnerabilities.

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [0.0.8] - 2025-11-14
### Changed
- Disabled thinking for Google Models

## [0.0.8] - 2025-11-12
### Changed
- Navbar spacing rules

### Removed
- banner from app pages


## [0.0.8] - 2025-11-09
### Added
- `deleted_at` field for the BaseModel to support soft_deletion where necessary.
- Add soft_delete method on BaseModel

### Changed
- Rafctor of agents and utils.
- Post cateogries now have separate pages.

## [0.0.8] - 2025-11-07
### Added
- Table of contents to Project Settings Page (only shows h2 headings)
- OG Image generation for generated posts
- Handle link of an image in submit blog post endpoint
- Vectors to ProjecPages and Competitors

### Fixed
- Cloudlfare Turnstyle now actaully does stuff
- Competitor table scrolling on mobile
- Toggle switches on settings page now use consistent dark gray color

## [0.0.8] - 2025-11-04
### Added
- Docs section

## [0.0.7] - 2025-11-02
### Changed
- Project UI updated to be more intuitive.
- PydanticAI library upgrade.

### Added
- Copy as HTML on Generated Blog Posts.
- PDF Generation for blog posts.
- Centralized location of all AI models used in the app.
- Referrer model to display banners for expected referrer like producthunt
- Competitors page to view all competitors for any given project

## [0.0.7] - 2025-11-01
### Changed
- update to user-settings page
- Enhanced blog post generation to intelligently use project pages based on `always_use` flag

### Added
- sitemaps support
- project pages in the ui for projects
- add the ability to select which project pages will always be used in project generations.
- blog posts use project pages more intelligently with two-tier system:
  - Required pages (always_use=True) must be linked in generated content
  - Optional pages are suggested for AI to use intelligently based on relevance


## [0.0.7] - 2025-10-29
## Changed
- Fixed and improved all limitations based on plans.
- styling and info about pricing on the user-settings page
- more accurate logic for how many ideas are generated when clicked "Generate more"
- Don't let people create project from url that has been added previously
- superusers are considered to have a subscription
- landing page and home page are different.

## Added
- Cloudflare turnstile and remove blocking project creation for uncofirmed emails.
- Onboarding Flow
- Add MJML for custom emails.
- admin panel page


## [0.0.7] - 2025-10-14
## Changed
- Landing page design + content


## [0.0.7] - 2025-10-13
**Added**
- new validation to see if content start with a header


## [0.0.7] - 2025-10-12
**Changes**
- how logs are sent to sentry


## [0.0.7] - 2025-10-10
**Added**
- a few keywords for placeholder image/link detection


## [0.0.7] - 2025-10-06
**Added**
- page to show publish history

**Change**
- Generate More Ideas now shows up all the time

**Fixed**
- actually run validations now


## [0.0.7] - 2025-10-04
**Added**
- Check that will make sure blog post is valid before submitting to endpoint.
- Endpoint to Fix the validation errors.
- Self fixing for Content generated in an automated task.
- Target Keywords that are generated in a Title Suggestion, now get saved to project keywords.
- You can hover over a Target keyword to get summary stats.
- You will now see which keywords are being use
- You can now set keywords to use from the Title Suggestions view
- Google Auth
- Added a way to delete projects (irreversably)

**Fixed**
- link to the generated blog post upon creation
- if we failed to get project content and analyze it, delete the project


## [0.0.6] - 2025-09-15
**Fixed**
- Github login not showing up.


## [0.0.6] - 2025-09-15
**Added**
- Instruction on how to deploy via docker compose and pure python/django.

**Changed**
- The name of the app to 'TuxSSEO'.


## [0.0.5] - 2025-09-08
**Added**
- Automatic super-simple deployment via Render


## [0.0.4] - 2025-08-19
**Added**
- More info on the Generated Blog Post page, as well as the post button.
- Keywords:
  - Separate page with keywords for each project
  - Ability to select which keywords will be used in post generation
  - Ablity to sort the table
  - Converted keyword addition form to modal interface for cleaner UI
  - Get more "People also search for" and "Related" keywords
  - allow users to delete keywords
- My name to generated blog posts
- Disbale project creation for unverified users
- More logs for content generation to better track progress

**Changed**

## [0.0.4] - 2025-08-18
**Added**
- Added a couple of logs to Django Ninja Auth module and Submit Post endpoint

**Removed**
- Logging config for django-q module as I suspect it was messing with the Sentry Error logging
- Excessive details in the logs

**Changed**
- Authneticate classes in auth.py to follow proper way from django-ninja docs
- Genereate Content prompts
- Design of the Title Suggestion card to be a little more visually appealing, plus added date

## [0.0.4] - 2025-08-17
**Added**
- Group name to submit blog post task

**Fixed**
- Error Reporting for Django-Q2


## [0.0.4] - 2025-08-15
**Fixed**
- `generate_and_post_blog_post` UnboundLocalError
- UI on the user-settings page, plus issue with Update Subscription links
- UI on the login and signup pages
- Saving the Auto Posting setting


## [0.0.3] - 2025-08-10
**Removed**
- Various agents, focus on generating blog post content
- PricingPageAnalysis and CompetitorBlog post models
- Views for now unsporrted models
- Posthog Alias Creation in HomePageView

**Changed**
- Simplification of the design and the UI

**Added**
- A page for generated content

## [0.0.1] - 2025-08-09
**Added**
- Adding automated posting feature

**Fixed**
- `last_posted_blog_post` fixed when don't exist
- Schedule post if there are no posts from the past
