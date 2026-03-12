---
title: Public API Architecture
description: How TuxSEO separates external public automation APIs from internal app APIs.
---

## Overview

TuxSEO now has two API surfaces:

- Internal API: `/api/*` for first-party web app behavior.
- Public API: `/public-api/*` for external automation clients.

This separation keeps internal endpoints stable for product development
while giving external users a focused contract.

## Public API Module

The public surface lives in `core/public_api` and has its own:

- auth layer (`X-API-Key` header)
- request/response schemas
- route handlers
- OpenAPI schema and docs UI

## Initial Public Endpoints

- `GET /public-api/account`
- `POST /public-api/projects`
- `POST /public-api/projects/{project_id}/content-automation`

These endpoints cover account introspection, project onboarding, and content automation setup.

## Documentation Exposure

Public docs are available at:

- `GET /public-api/docs`
- `GET /public-api/openapi.json`

Internal OpenAPI docs are disabled to avoid exposing private-first route contracts.

## Design Notes

- Internal API handlers remain unchanged for existing app flows.
- Public handlers reuse existing models and business rules where possible.
- Validation happens at schema and endpoint layers with explicit error responses.
