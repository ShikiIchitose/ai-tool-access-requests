from __future__ import annotations

from io import StringIO
from typing import cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.core.management import call_command
from django.test import TestCase, override_settings

from access_requests.models import AccessRequest, AITool

User = get_user_model()


@override_settings(
    DEMO_REQUESTER_USERNAME="demo-requester",
    DEMO_REVIEWER_USERNAME="demo-reviewer",
)
class ResetDemoStateCommandTests(TestCase):
    BASELINE_TOOL_CODES = {
        "chatgpt-enterprise",
        "claude-enterprise",
        "gemini-enterprise",
    }

    def setUp(self) -> None:
        self.user_manager = cast(UserManager, User.objects)
        call_command("ensure_demo_state", stdout=StringIO())

    def _create_extra_tool(self) -> AITool:
        return AITool.objects.create(
            code="temp-extra-tool",
            name="Temporary Extra Tool",
            vendor="Test Vendor",
            description="Temporary tool for reset command tests.",
            homepage_url="https://example.com/temp-extra-tool",
            is_active=True,
        )

    def _create_extra_request(self, *, tool: AITool) -> AccessRequest:
        requester = self.user_manager.create_user(
            username="extra-requester",
            password="test-password-123",
        )
        return AccessRequest.objects.create(
            requester=requester,
            ai_tool=tool,
            purpose="Temporary request for reset command tests",
            business_justification="Used to verify reset_demo_state behavior.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
            status=AccessRequest.Status.PENDING,
        )

    def _run_command(self, **options: object) -> str:
        stdout = StringIO()
        call_command("reset_demo_state", stdout=stdout, **options)
        return stdout.getvalue()

    def test_reset_demo_state_dry_run_does_not_modify_database(self) -> None:
        extra_tool = self._create_extra_tool()
        self._create_extra_request(tool=extra_tool)

        before_request_count = AccessRequest.objects.count()
        before_tool_count = AITool.objects.count()

        output = self._run_command(
            dry_run=True,
            preserve_tools=False,
            verbosity=1,
        )

        self.assertIn("Dry run only. No rows were deleted.", output)
        self.assertEqual(AccessRequest.objects.count(), before_request_count)
        self.assertEqual(AITool.objects.count(), before_tool_count)
        self.assertTrue(
            AccessRequest.objects.filter(
                requester__username="extra-requester",
                ai_tool__code="temp-extra-tool",
            ).exists()
        )
        self.assertTrue(AITool.objects.filter(code="temp-extra-tool").exists())

    def test_reset_demo_state_preserves_tools_by_default(self) -> None:
        extra_tool = self._create_extra_tool()
        self._create_extra_request(tool=extra_tool)

        output = self._run_command(
            no_input=True,
            verbosity=1,
        )

        self.assertIn("Deleted AITool rows: 0 (preserved)", output)
        self.assertEqual(AccessRequest.objects.count(), 3)
        self.assertEqual(
            set(AccessRequest.objects.values_list("status", flat=True)),
            {
                AccessRequest.Status.PENDING,
                AccessRequest.Status.APPROVED,
                AccessRequest.Status.REJECTED,
            },
        )
        self.assertTrue(AITool.objects.filter(code="temp-extra-tool").exists())
        self.assertEqual(
            set(AITool.objects.values_list("code", flat=True)),
            self.BASELINE_TOOL_CODES | {"temp-extra-tool"},
        )

    def test_reset_demo_state_no_preserve_tools_reseeds_tools(self) -> None:
        extra_tool = self._create_extra_tool()
        self._create_extra_request(tool=extra_tool)

        output = self._run_command(
            no_input=True,
            preserve_tools=False,
            verbosity=1,
        )

        self.assertIn("Demo state reset completed successfully.", output)
        self.assertEqual(AccessRequest.objects.count(), 3)
        self.assertEqual(
            set(AccessRequest.objects.values_list("status", flat=True)),
            {
                AccessRequest.Status.PENDING,
                AccessRequest.Status.APPROVED,
                AccessRequest.Status.REJECTED,
            },
        )
        self.assertFalse(AITool.objects.filter(code="temp-extra-tool").exists())
        self.assertEqual(
            set(AITool.objects.values_list("code", flat=True)),
            self.BASELINE_TOOL_CODES,
        )

    def test_reset_demo_state_verbosity_2_shows_preview(self) -> None:
        extra_tool = self._create_extra_tool()
        self._create_extra_request(tool=extra_tool)

        output = self._run_command(
            dry_run=True,
            verbosity=2,
        )

        self.assertIn("Dry run only. No rows were deleted.", output)
        self.assertIn("Preview of up to 5 AccessRequest rows:", output)
        self.assertIn("requester=extra-requester", output)
        self.assertIn("tool=temp-extra-tool", output)
        self.assertIn(f"status={AccessRequest.Status.PENDING}", output)
