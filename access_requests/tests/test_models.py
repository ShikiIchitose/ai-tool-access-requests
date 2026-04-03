from __future__ import annotations

from typing import cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import UserManager
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from access_requests.models import AccessRequest, AITool

User = get_user_model()


class AccessRequestModelTests(TestCase):
    def setUp(self) -> None:
        user_manager = cast(UserManager, User.objects)

        self.requester = user_manager.create_user(
            username="requester",
            password="test-password-123",
        )
        self.reviewer = user_manager.create_user(
            username="reviewer",
            password="test-password-456",
        )

        self.tool = AITool.objects.create(
            code="chatgpt-enterprise",
            name="ChatGPT Enterprise",
            vendor="OpenAI",
            description="Enterprise AI assistant",
            is_active=True,
        )

    def _build_request(
        self,
        **overrides: object,
    ) -> AccessRequest:
        data: dict[str, object] = {
            "requester": self.requester,
            "ai_tool": self.tool,
            "purpose": "Internal drafting support",
            "business_justification": "Needed for faster internal document work.",
            "data_classification": AccessRequest.DataClassification.INTERNAL,
            "notes": "",
            "status": AccessRequest.Status.PENDING,
            "review_comment": "",
            "reviewed_by": None,
            "reviewed_at": None,
        }
        data.update(overrides)
        return AccessRequest(**data)

    def test_status_choices_are_expected(self) -> None:
        self.assertEqual(
            {value for value, _label in AccessRequest.Status.choices},
            {
                AccessRequest.Status.PENDING,
                AccessRequest.Status.APPROVED,
                AccessRequest.Status.REJECTED,
            },
        )

    def test_duplicate_pending_request_is_blocked_by_database_constraint(self) -> None:
        AccessRequest.objects.create(
            requester=self.requester,
            ai_tool=self.tool,
            purpose="First pending request",
            business_justification="First request justification.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
            status=AccessRequest.Status.PENDING,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccessRequest.objects.create(
                    requester=self.requester,
                    ai_tool=self.tool,
                    purpose="Second pending request",
                    business_justification="Second request justification.",
                    data_classification=AccessRequest.DataClassification.INTERNAL,
                    notes="",
                    status=AccessRequest.Status.PENDING,
                )

    def test_reviewed_request_does_not_block_new_pending_request(self) -> None:
        AccessRequest.objects.create(
            requester=self.requester,
            ai_tool=self.tool,
            purpose="Already approved request",
            business_justification="Previously approved.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
            status=AccessRequest.Status.APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
            review_comment="Approved previously.",
        )

        pending_request = AccessRequest.objects.create(
            requester=self.requester,
            ai_tool=self.tool,
            purpose="New pending request",
            business_justification="Needs access again for a new use case.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
            status=AccessRequest.Status.PENDING,
        )

        self.assertEqual(AccessRequest.objects.count(), 2)
        self.assertEqual(pending_request.status, AccessRequest.Status.PENDING)

    def test_full_clean_rejects_pending_request_with_review_metadata(self) -> None:
        access_request = self._build_request(
            status=AccessRequest.Status.PENDING,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            access_request.full_clean()

    def test_full_clean_rejects_approved_request_without_reviewer(self) -> None:
        access_request = self._build_request(
            status=AccessRequest.Status.APPROVED,
            reviewed_by=None,
            reviewed_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            access_request.full_clean()

    def test_full_clean_rejects_approved_request_without_reviewed_at(self) -> None:
        access_request = self._build_request(
            status=AccessRequest.Status.APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=None,
        )

        with self.assertRaises(ValidationError):
            access_request.full_clean()

    def test_full_clean_rejects_rejected_request_without_reviewer(self) -> None:
        access_request = self._build_request(
            status=AccessRequest.Status.REJECTED,
            review_comment="Needs more detail.",
            reviewed_by=None,
            reviewed_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            access_request.full_clean()

    def test_full_clean_rejects_rejected_request_without_reviewed_at(self) -> None:
        access_request = self._build_request(
            status=AccessRequest.Status.REJECTED,
            review_comment="Needs more detail.",
            reviewed_by=self.reviewer,
            reviewed_at=None,
        )

        with self.assertRaises(ValidationError):
            access_request.full_clean()
