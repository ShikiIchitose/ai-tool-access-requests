from __future__ import annotations

import argparse

from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction

from access_requests.models import AccessRequest, AITool

_CONFIRM_TEXT = "reset-demo"
_PREVIEW_LIMIT = 5


class Command(BaseCommand):
    help = (
        "Reset the public demo surface to a clean baseline and reseed it "
        "via ensure_demo_state."
    )
    requires_migrations_checks = True

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Run non-interactively. Required for Render Cron Jobs.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without modifying the database.",
        )
        parser.add_argument(
            "--preserve-tools",
            action=argparse.BooleanOptionalAction,
            default=True,
            help=(
                "Preserve existing AITool rows by default. "
                "Use --no-preserve-tools to delete and reseed them."
            ),
        )

    def handle(self, *args, **options) -> None:
        no_input: bool = options["no_input"]
        dry_run: bool = options["dry_run"]
        preserve_tools: bool = options["preserve_tools"]
        verbosity: int = options["verbosity"]

        request_count = AccessRequest.objects.count()
        tool_count = 0 if preserve_tools else AITool.objects.count()

        if verbosity >= 3:
            self.stdout.write(
                "Options: "
                f"no_input={no_input}, "
                f"dry_run={dry_run}, "
                f"preserve_tools={preserve_tools}, "
                f"verbosity={verbosity}"
            )

        if dry_run:
            if verbosity >= 1:
                self.stdout.write(
                    self.style.WARNING("Dry run only. No rows were deleted.")
                )
                self.stdout.write(f"AccessRequest rows to delete: {request_count}")
                if preserve_tools:
                    self.stdout.write("AITool rows to delete: 0 (preserved)")
                else:
                    self.stdout.write(f"AITool rows to delete: {tool_count}")

            if verbosity >= 2:
                preview_requests = list(
                    AccessRequest.objects.select_related(
                        "requester", "ai_tool"
                    ).order_by("id")[:_PREVIEW_LIMIT]
                )

                if preview_requests:
                    self.stdout.write(
                        f"Preview of up to {_PREVIEW_LIMIT} AccessRequest rows:"
                    )
                    for access_request in preview_requests:
                        self.stdout.write(
                            "  - "
                            f"id={access_request.id}, "
                            f"requester={access_request.requester.username}, "
                            f"tool={access_request.ai_tool.code}, "
                            f"status={access_request.status}"
                        )
                else:
                    self.stdout.write("No AccessRequest rows would be deleted.")

            return

        if not no_input:
            if verbosity >= 1:
                self.stdout.write(
                    self.style.WARNING(
                        "This command will delete demo requests"
                        + ("" if preserve_tools else " and demo tools")
                        + " and then reseed the baseline with ensure_demo_state."
                    )
                )
            answer = input(f"Type '{_CONFIRM_TEXT}' to continue: ").strip()
            if answer != _CONFIRM_TEXT:
                raise CommandError("Aborted.")

        if verbosity >= 2:
            self.stdout.write("Starting reset_demo_state...")

        with transaction.atomic():
            if verbosity >= 2:
                self.stdout.write("Deleting AccessRequest rows...")

            deleted_requests, _ = AccessRequest.objects.all().delete()

            if verbosity >= 1:
                self.stdout.write(f"Deleted AccessRequest rows: {deleted_requests}")

            if preserve_tools:
                if verbosity >= 1:
                    self.stdout.write("Deleted AITool rows: 0 (preserved)")
            else:
                if verbosity >= 2:
                    self.stdout.write("Deleting AITool rows...")
                deleted_tools, _ = AITool.objects.all().delete()
                if verbosity >= 1:
                    self.stdout.write(f"Deleted AITool rows: {deleted_tools}")

            if verbosity >= 2:
                self.stdout.write("Calling ensure_demo_state...")

            call_command(
                "ensure_demo_state",
                verbosity=verbosity,
            )

            if verbosity >= 2:
                self.stdout.write("ensure_demo_state finished.")

        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS("Demo state reset completed successfully.")
            )
