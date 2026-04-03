from __future__ import annotations

from typing import cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, UserManager
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access_requests.models import AccessRequest, AITool

User = get_user_model()


class AccessRequestAdminPermissionTests(TestCase):
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

        self.staff_with_view = user_manager.create_user(
            username="staff_with_view",
            password="test-password-789",
            is_staff=True,
        )
        self.staff_without_view = user_manager.create_user(
            username="staff_without_view",
            password="test-password-000",
            is_staff=True,
        )

        self.tool = AITool.objects.create(
            code="chatgpt-enterprise",
            name="ChatGPT Enterprise",
            vendor="OpenAI",
            description="Enterprise AI assistant",
            is_active=True,
        )

        self.access_request = AccessRequest.objects.create(
            requester=self.requester,
            ai_tool=self.tool,
            purpose="Internal drafting support",
            business_justification="Needed for internal documentation work.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
            status=AccessRequest.Status.APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
            review_comment="Approved for internal use.",
        )

        content_type = ContentType.objects.get_for_model(AccessRequest)
        view_permission = Permission.objects.get(
            content_type=content_type,
            codename="view_accessrequest",
        )
        self.staff_with_view.user_permissions.add(view_permission)

    def _changelist_url(self) -> str:
        return reverse("admin:access_requests_accessrequest_changelist")

    def _change_url(self) -> str:
        return reverse(
            "admin:access_requests_accessrequest_change",
            args=[self.access_request.pk],
        )

    def test_staff_with_view_permission_can_open_access_request_changelist(
        self,
    ) -> None:
        self.client.force_login(self.staff_with_view)

        response = self.client.get(self._changelist_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approved")

    def test_staff_without_view_permission_cannot_open_access_request_changelist(
        self,
    ) -> None:
        self.client.force_login(self.staff_without_view)

        response = self.client.get(self._changelist_url())

        self.assertEqual(response.status_code, 403)

    def test_staff_with_view_permission_can_open_access_request_detail_in_view_only_mode(
        self,
    ) -> None:
        self.client.force_login(self.staff_with_view)

        response = self.client.get(self._change_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Approved")
        self.assertNotContains(response, 'name="_save"')
        self.assertNotContains(response, 'name="_continue"')

    def test_staff_without_view_permission_cannot_open_access_request_detail(
        self,
    ) -> None:
        self.client.force_login(self.staff_without_view)

        response = self.client.get(self._change_url())

        self.assertEqual(response.status_code, 403)


class AccessRequestAdminBehaviorTests(TestCase):
    def setUp(self) -> None:
        user_manager = cast(UserManager, User.objects)

        self.superuser = user_manager.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password-123",
        )
        self.requester = user_manager.create_user(
            username="requester",
            password="test-password-456",
        )
        self.reviewer = user_manager.create_user(
            username="reviewer",
            password="test-password-789",
        )

        self.tool = AITool.objects.create(
            code="chatgpt-enterprise",
            name="ChatGPT Enterprise",
            vendor="OpenAI",
            description="Enterprise AI assistant",
            is_active=True,
        )

        self.access_request = AccessRequest.objects.create(
            requester=self.requester,
            ai_tool=self.tool,
            purpose="Internal drafting support",
            business_justification="Needed for internal documentation work.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
            status=AccessRequest.Status.PENDING,
        )

    def _add_url(self) -> str:
        return reverse("admin:access_requests_accessrequest_add")

    def _change_url(self) -> str:
        return reverse(
            "admin:access_requests_accessrequest_change",
            args=[self.access_request.pk],
        )

    def _delete_url(self) -> str:
        return reverse(
            "admin:access_requests_accessrequest_delete",
            args=[self.access_request.pk],
        )

    def test_access_request_add_is_denied_even_for_superuser(self) -> None:
        self.client.force_login(self.superuser)

        response = self.client.get(self._add_url())

        self.assertEqual(response.status_code, 403)

    def test_access_request_delete_is_denied_even_for_superuser(self) -> None:
        self.client.force_login(self.superuser)

        response = self.client.get(self._delete_url())

        self.assertEqual(response.status_code, 403)

    def test_access_request_change_post_is_denied_and_object_is_unchanged(
        self,
    ) -> None:
        self.client.force_login(self.superuser)

        response = self.client.post(
            self._change_url(),
            data={
                "status": AccessRequest.Status.REJECTED,
                "review_comment": "Attempted admin-side rejection.",
            },
        )

        self.assertEqual(response.status_code, 403)

        self.access_request.refresh_from_db()
        self.assertEqual(self.access_request.status, AccessRequest.Status.PENDING)
        self.assertEqual(self.access_request.review_comment, "")
        self.assertIsNone(self.access_request.reviewed_by)
        self.assertIsNone(self.access_request.reviewed_at)


class AIToolAdminTests(TestCase):
    def setUp(self) -> None:
        user_manager = cast(UserManager, User.objects)

        self.superuser = user_manager.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password-123",
        )

        self.tool = AITool.objects.create(
            code="chatgpt-enterprise",
            name="ChatGPT Enterprise",
            vendor="OpenAI",
            description="Enterprise AI assistant",
            is_active=True,
        )

    def _delete_url(self) -> str:
        return reverse(
            "admin:access_requests_aitool_delete",
            args=[self.tool.pk],
        )

    def test_ai_tool_delete_is_denied_even_for_superuser(self) -> None:
        self.client.force_login(self.superuser)

        response = self.client.get(self._delete_url())

        self.assertEqual(response.status_code, 403)
