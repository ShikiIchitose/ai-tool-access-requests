from __future__ import annotations

from typing import cast

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.test import TestCase
from django.utils import timezone

from access_requests.forms import AccessRequestCreateForm, ReviewDecisionForm
from access_requests.models import AccessRequest, AITool

User = get_user_model()


class AccessRequestCreateFormTests(TestCase):
    def setUp(self) -> None:
        user_manager = cast(UserManager, User.objects)

        self.user = user_manager.create_user(
            username="requester",
            password="test-password-123",
        )
        self.reviewer = user_manager.create_user(
            username="reviewer",
            password="test-password-123",
        )

        self.active_tool = AITool.objects.create(
            code="chatgpt-enterprise",
            name="ChatGPT Enterprise",
            vendor="OpenAI",
            description="Enterprise LLM access",
            is_active=True,
        )
        self.inactive_tool = AITool.objects.create(
            code="legacy-ai-tool",
            name="Legacy AI Tool",
            vendor="Example Vendor",
            description="Inactive tool",
            is_active=False,
        )

    def _valid_form_data(self, **overrides: object) -> dict[str, object]:
        data: dict[str, object] = {
            "ai_tool": self.active_tool.pk,
            "purpose": "Draft internal technical documents",
            "business_justification": "Needed for faster documentation work.",
            "data_classification": AccessRequest.DataClassification.INTERNAL,
            "notes": "Used only for internal documentation tasks.",
        }
        data.update(overrides)
        return data

    def test_unbound_form_shows_only_active_tools(self) -> None:
        form = AccessRequestCreateForm(user=self.user)
        ai_tool_field = cast(forms.ModelChoiceField, form.fields["ai_tool"])

        assert ai_tool_field.queryset is not None
        self.assertEqual(list(ai_tool_field.queryset), [self.active_tool])

    def test_inactive_tool_is_rejected_on_manual_post(self) -> None:
        form = AccessRequestCreateForm(
            data=self._valid_form_data(ai_tool=self.inactive_tool.pk),
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("ai_tool", form.errors)
        error = form.errors.as_data()["ai_tool"][0]
        self.assertIn("inactive", error.message.lower())

    def test_duplicate_pending_request_is_rejected(self) -> None:
        AccessRequest.objects.create(
            requester=self.user,
            ai_tool=self.active_tool,
            purpose="Existing pending request",
            business_justification="Already requested.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
            status=AccessRequest.Status.PENDING,
        )

        form = AccessRequestCreateForm(
            data=self._valid_form_data(),
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
        non_field_error = form.errors.as_data()["__all__"][0]
        self.assertIn("already exists", non_field_error.message.lower())

    def test_existing_reviewed_request_does_not_block_new_request(self) -> None:
        AccessRequest.objects.create(
            requester=self.user,
            ai_tool=self.active_tool,
            purpose="Old approved request",
            business_justification="Already processed.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
            status=AccessRequest.Status.APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
            review_comment="Approved previously.",
        )

        form = AccessRequestCreateForm(
            data=self._valid_form_data(),
            user=self.user,
        )

        self.assertTrue(form.is_valid())


class ReviewDecisionFormTests(TestCase):
    def test_approve_without_comment_is_valid(self) -> None:
        form = ReviewDecisionForm(
            data={
                "decision": ReviewDecisionForm.Decision.APPROVE,
                "review_comment": "",
            }
        )

        self.assertTrue(form.is_valid())

    def test_reject_without_comment_is_invalid(self) -> None:
        form = ReviewDecisionForm(
            data={
                "decision": ReviewDecisionForm.Decision.REJECT,
                "review_comment": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("review_comment", form.errors)

    def test_reject_with_comment_is_valid(self) -> None:
        form = ReviewDecisionForm(
            data={
                "decision": ReviewDecisionForm.Decision.REJECT,
                "review_comment": "This request needs more justification.",
            }
        )

        self.assertTrue(form.is_valid())
