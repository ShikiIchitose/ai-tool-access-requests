#!/usr/bin/env bash
set -o errexit

uv sync --locked --no-dev
uv run python manage.py collectstatic --no-input
uv run python manage.py migrate
