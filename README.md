# ai-tool-access-requests

> 日本語版: [README.ja.md](README.ja.md)

A minimal Django + PostgreSQL internal workflow application for requesting and reviewing access to enterprise AI tools.

This repository is a portfolio project built to demonstrate practical backend fundamentals with Django: authentication, authorization, relational modeling, form validation, class-based views, operational admin design, and test-backed protection of core business rules. The scope is intentionally small, but the workflow is meant to resemble a realistic internal business application rather than a generic CRUD demo.

The screenshots below show the two main user perspectives in the application: requester-facing request tracking and reviewer-facing review workflow.

## UI preview

| Requester-facing view | Reviewer-facing view |
| --- | --- |
| <img src="docs/images/my-requests-dark.png" alt="Requester-facing My requests page showing submitted requests and their current statuses" width="100%"> | <img src="docs/images/review-queue-dark.png" alt="Reviewer-facing Review queue page showing pending requests and review actions" width="100%"> |
| *Tracking submitted requests and their current statuses from the requester-facing view.* | *Reviewing pending requests through a dedicated reviewer-facing queue, ordered oldest first.* |

## Live demo

A public demo deployment is available here:

- [Live demo](https://ai-tool-access-requests.onrender.com/)

This demo is intended to make the requester-facing and reviewer-facing workflows easy to evaluate without creating local accounts first.

## Portfolio demo access

The login page includes **portfolio demo access** buttons in addition to the standard username/password form.

Public demo roles:

- **Demo requester**
  - browse active AI tools
  - submit a new access request
  - view requester-facing request history

- **Demo reviewer**
  - open the reviewer-only queue
  - inspect pending requests
  - execute approve or reject decisions through the dedicated review UI

Notes:

- The public demo exposes only the requester and reviewer perspectives.
- **Django admin is not part of the public demo surface.**
- This demo access flow is a portfolio convenience feature for evaluation, not a production authentication pattern.

## Seeded demo state

The public demo includes a small seeded dataset so the main flows are immediately visible.

Included demo state:

- active tools for:
  - ChatGPT Enterprise
  - Claude Enterprise
  - Gemini Enterprise
- at least one reviewer-visible `pending` request
- at least one `approved` request
- at least one `rejected` request

The reviewer-visible pending request is intentionally seeded so that the review queue is usable immediately after demo reviewer login.

The demo state is not only seeded for first-time visibility, but also designed to be reset back to a known baseline after public interaction.

This is handled through two separate management commands:

- `ensure_demo_state`
  - provisions the baseline demo users, reviewer-group membership, active demo tools, and seeded requests

- `reset_demo_state`
  - clears public demo request data
  - optionally re-seeds tools when needed
  - delegates baseline reconstruction back to `ensure_demo_state`

By default, `reset_demo_state` preserves the seeded `AITool` catalog and resets the request-side demo data only. This keeps normal public-demo maintenance lightweight while still allowing a full baseline rebuild when needed.

## How to try the demo

### Requester flow

1. Open the live demo.
2. On `/login/`, select **Continue as demo requester**.
3. Browse the tool catalog.
4. Create a new access request for an active tool.
5. Open **My requests** to inspect submitted requests and their statuses.

### Reviewer flow

1. Open the live demo.
2. On `/login/`, select **Continue as demo reviewer**.
3. Open the review queue.
4. Inspect a pending request that is ready for review.
5. Approve or reject it through the dedicated reviewer-facing screen.

## What this project demonstrates

- Practical use of Django built-in features
- Authentication and authorization with role-aware behavior
- Relational modeling with PostgreSQL
- Request and review workflow design
- Form validation and server-side business rule enforcement
- Clear separation between requester-facing, reviewer-facing, and admin responsibilities
- Inspection-only admin design for sensitive workflow records
- A focused automated test suite that protects the application's core behavior against regressions
- A thin, environment-gated demo access layer added without re-architecting the core authentication model

## Project overview

In this application:

- an authenticated user can browse an internal catalog of AI tools
- a requester can submit an access request for an active tool
- a requester can view only their own submitted requests
- a reviewer can inspect pending requests and approve or reject them
- Django admin is used for operational maintenance and safe inspection, not as an alternate workflow execution surface

The project keeps the domain model intentionally minimal:

- Django built-in `User`
- `AITool`
- `AccessRequest`

It also keeps the role model explicit:

- **requester**: a normal authenticated user
- **reviewer**: a user in `Group(name="reviewer")`
- **admin operator**: a user with `is_staff=True` for Django admin access
- **system owner**: a superuser with full system permissions

This separation is deliberate. Business workflow roles and Django system flags are treated as related but distinct concerns.

## Core workflow

1. An authenticated user browses the active AI tool catalog.
2. The user submits an access request with a purpose and business justification.
3. The requester can view only their own submitted requests and current status.
4. A reviewer sees a pending review queue, excluding their own requests.
5. The reviewer approves or rejects the request through a dedicated review UI.
6. Django admin is used to maintain the tool catalog and inspect request records in a safe, view-only manner.

## Key business rules

This project is intentionally small, but it includes several important workflow boundaries:

- **Requester-facing and reviewer-facing routes are separated**
  - `/requests/<pk>/` is owner-only
  - `/reviews/<pk>/` is reviewer-only

- **Self-review is forbidden**
  - reviewers cannot review their own submitted requests
  - self-owned pending requests are excluded from the review queue
  - direct review access and review POST actions are denied for self-review attempts

- **Only pending requests are reviewable**
  - once approved or rejected, the same request cannot be reviewed again

- **Duplicate pending requests are prevented**
  - the same user cannot hold multiple simultaneous `pending` requests for the same tool
  - this is protected both at the form layer and at the database layer

- **Inactive tools are not requestable**
  - inactive tools are hidden from requester-facing flows
  - manual POST attempts using inactive tools are rejected server-side

- **Admin is inspection-oriented**
  - `AITool` is operationally managed in Django admin
  - `AccessRequest` is treated as inspection-only in admin
  - request approval or rejection is not executed through admin

The goal is to show not just CRUD mechanics, but careful handling of permission boundaries and workflow safety.

## Why the test suite matters

This repository includes a **minimal but meaningful automated test suite** focused on the parts of the application that are most likely to break the workflow when the code evolves.

The aim is not broad but shallow coverage. Instead, the test suite focuses on protecting the core business rules:

- form validation
- requester and reviewer route separation
- permission boundaries
- self-review prohibition
- inactive tool handling
- model-level consistency
- database-backed duplicate pending protection
- inspection-only admin behavior
- portfolio demo login behavior and deployment-state expectations

The tests are organized by responsibility:

- `test_forms.py`
  - input validation
  - inactive tool rejection
  - duplicate pending request rejection
  - rejection comment requirement

- `test_views.py`
  - route protection
  - role-aware access control
  - requester and reviewer flow boundaries
  - approval and rejection workflow behavior
  - re-review prevention
  - self-review protection

- `test_models.py`
  - status choices
  - model consistency validation
  - database constraint behavior for duplicate pending requests

- `test_admin.py`
  - permission boundaries in Django admin
  - inspection-only behavior for `AccessRequest`
  - protection against admin-side workflow bypass

- `test_auth_demo.py`
  - demo login page rendering
  - requester and reviewer demo login behavior
  - safe `next` redirect handling
  - disabled-feature and missing-demo-user behavior
  - `ensure_demo_state` provisioning expectations

- `test_reset_demo_state.py`
  - verifies that `--dry-run` does not modify the database
  - verifies that seeded tools are preserved by default
  - verifies optional full tool re-seeding with `--no-preserve-tools`
  - verifies preview-oriented output behavior for higher verbosity levels

In other words, the test suite is intentionally aimed at reducing the chance that routine refactors or operational changes will break request creation, review execution, permission boundaries, admin safety, the portfolio demo access surface, or the reproducible reset behavior of the public demo environment.

## Current test status

- 68 tests passing

This includes the core workflow test suite as well as dedicated coverage for the portfolio demo login flow, including enabled and disabled rendering, safe `next` handling, demo-state provisioning expectations, and reproducible public demo reset behavior.

## Tech stack

- Python 3.13
- Django 6.0
- PostgreSQL
- psycopg 3
- uv
- Django templates and forms
- Django admin
- Gunicorn + Uvicorn worker
- WhiteNoise
- dj-database-url

## Architecture notes

### Minimal domain model

The project uses a deliberately small relational model centered on `ForeignKey` relationships:

- `AccessRequest.requester -> User`
- `AccessRequest.reviewed_by -> User`
- `AccessRequest.ai_tool -> AITool`

This keeps the initial release easy to reason about while still supporting a realistic request and review workflow. Future extensions such as employee profiles, reviewer scopes, or classification tags are intentionally deferred.

### Layer responsibilities

The project deliberately spreads responsibilities across layers:

- **model and database layer**
  - structural consistency
  - constraints
  - referential integrity

- **form layer**
  - input validation
  - duplicate detection for user feedback
  - rejection comment requirement

- **view layer**
  - authentication and authorization
  - object-level access control
  - workflow execution
  - safe handling of review decisions

- **admin layer**
  - operational visibility
  - catalog maintenance
  - safe inspection rather than workflow execution

This separation is important because the project is meant to show that backend design is not only about making pages work, but also about assigning rules to the correct layer.

## Local setup

### Prerequisites

- Python 3.13
- PostgreSQL running locally
- `uv`

For v0.1.0, PostgreSQL is expected to run locally rather than through Docker.

### Install dependencies

```bash
uv sync
```

### Configure environment variables

Create a local environment file from `.env.example` and set values that match your local setup.

One possible example:

```bash
cp .env.example .env.local
set -a
source .env.local
set +a
```

This project now uses a single `DATABASE_URL` setting for database configuration.

Example local values:

```env
DATABASE_URL=postgresql://your_db_user:your_db_password@127.0.0.1:5432/your_db_name
DJANGO_SECRET_KEY=<replace-this-with-a-real-secret>
DJANGO_DEBUG=true
```

Notes:

- `.env.example` is a local setup template for developers cloning the repository.
- It is not read automatically by Render.
- For deployed environments, set environment variables in the Render Dashboard.

### Apply migrations

```bash
uv run python manage.py migrate
```

### Create a superuser

```bash
uv run python manage.py createsuperuser
```

### Run the development server

```bash
uv run python manage.py runserver
```

## Initial reviewer and admin setup

After logging into Django admin:

1. Create a group named `reviewer`
2. Create or select a user who should act as a reviewer
3. Add that user to the `reviewer` group
4. Use `is_staff=True` only for users who should access Django admin
5. Grant the built-in model view permission where inspection access is needed in admin

This project intentionally does **not** treat `is_staff` alone as equivalent to reviewer permission. Review capability belongs to the business workflow role, not to admin access alone.

## Creating sample AI tools

You can create sample tools through Django admin.

Recommended example fields:

- `code`: URL-safe stable slug
- `name`: product name
- `vendor`: vendor name
- `description`: short internal description
- `homepage_url`: official product page
- `is_active`: active or inactive flag

Normal operation is based on **soft deactivation** with `is_active=False` rather than deleting tools.

## Demo Deployment Configuration Notes

This portfolio project adopts a deployment-oriented configuration for its public demo environment.

The main environment variables assumed for the public demo environment are:

```env
DJANGO_SECRET_KEY=replace-with-a-strong-secret
DATABASE_URL=postgresql://...
PYTHON_VERSION=3.13.12
DJANGO_DEBUG=false

ENABLE_DEMO_LOGIN=true
DEMO_REQUESTER_USERNAME=demo-requester
DEMO_REVIEWER_USERNAME=demo-reviewer

DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SECURE_HSTS_SECONDS=0
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=false
DJANGO_SECURE_HSTS_PRELOAD=false
```

Notes:

- Database configuration is standardized on `DATABASE_URL`.
- `DJANGO_SECRET_KEY` is required by the application settings.
- `.env.example` is a template for local setup and is not consumed automatically by Render.
- `RENDER_EXTERNAL_HOSTNAME` and `RENDER_EXTERNAL_URL` are assumed to be provided by Render and are used by the settings layer for host and CSRF configuration.

This repository includes a deployment build script at the project root:

```bash
./build.sh
```

This script is configured to install locked production dependencies, run `collectstatic`, and apply migrations.

The public demo also assumes a reproducible seeded state managed through `ensure_demo_state`, including demo users, reviewer-group membership, active demo tools, and seeded pending, approved, and rejected requests.

### Public demo reset workflow

Because the public demo can be modified by visitors, the repository also includes a dedicated reset command for restoring the demo database state to a known baseline.

Typical manual usage from the Render Shell:

```bash
uv run python manage.py reset_demo_state --no-input
```

Useful variants:

```bash
uv run python manage.py reset_demo_state --dry-run
uv run python manage.py reset_demo_state --no-preserve-tools --no-input
```

Operational intent:

- normal reset keeps the seeded AI tool catalog intact
- request-side demo data is reset to baseline
- full tool re-seeding is available only when explicitly requested

This command is intended as a lightweight operational maintenance tool for the public portfolio demo rather than as part of the end-user workflow.

## Running tests

Run the full automated test suite with:

```bash
uv run pytest
```

Optional check:

```bash
uv run python manage.py check
```

The tests are intentionally focused on core workflow safety rather than cosmetic behavior. They are meant to catch regressions in the parts of the app that matter most:

- request creation rules
- review permission boundaries
- self-review prohibition
- model and database consistency
- admin-side safety
- demo login behavior in enabled and disabled deployment modes
- public demo reset reproducibility

## Scope and non-goals

The scope is intentionally constrained to keep the project minimal and coherent.

### Included in v0.1.0

- AI tool catalog browsing
- access request creation
- requester-facing request list and detail
- reviewer approval and rejection flow
- Django admin for catalog maintenance and safe request inspection

### Explicitly out of scope

- self-signup
- email notifications
- Slack notifications
- multi-step approval
- dedicated audit log table
- external API integrations
- public API
- Django REST Framework
- Docker and Docker Compose
- JavaScript-heavy rich UI
- custom user model

These exclusions are intentional. The goal of the project is to show a disciplined minimum viable product with realistic backend boundaries, not to maximize feature count.

## Future improvements

Natural next steps after this minimum viable product would include:

- invite-based onboarding or password-reset-driven account activation
- audit logging for sensitive workflow actions
- multi-step approval flows
- notifications
- reviewer scope extensions
- department or employee profile modeling
- an API layer for external integration
- deployment-oriented production hardening

## Why this project exists as a portfolio piece

This repository is meant to demonstrate that I can build a small but credible backend application with:

- a clear domain model
- explicit workflow rules
- practical Django conventions
- careful permission design
- operational awareness around admin usage
- focused tests that protect core behavior over time

The emphasis is on correctness, separation of concerns, and regression resistance in a realistic internal workflow, not on maximizing feature count or frontend complexity.

## License

MIT License. See `LICENSE` file.
