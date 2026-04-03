from datetime import timedelta
from typing import cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, UserManager
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access_requests.models import AccessRequest, AITool

User = get_user_model()


class AuthDashboardViewTests(TestCase):
    def setUp(self) -> None:
        user_manager = cast(UserManager, User.objects)
        self.user = user_manager.create_user(
            username="alice",
            password="test-pass-123",
        )

    def test_login_page_renders(self) -> None:
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")

    def test_dashboard_requires_login(self) -> None:
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

    def test_authenticated_user_can_open_dashboard(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "access_requests/dashboard.html")
        self.assertContains(response, "alice")

    def test_logout_via_post_redirects_to_login(self) -> None:
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))

    def test_dashboard_shows_requester_actions_for_authenticated_user(self) -> None:
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Browse AI tools")
        self.assertContains(response, "Create a new request")
        self.assertContains(response, "View my requests")
        self.assertNotContains(response, "Open review queue")

    def test_dashboard_shows_reviewer_actions_for_reviewer(self) -> None:
        reviewer_group = Group.objects.create(name="reviewer")
        self.user.groups.add(reviewer_group)

        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open review queue")
        self.assertContains(response, "Reviewer: Yes")

    def test_base_navigation_hides_review_link_for_non_reviewer(self) -> None:
        tool = AITool.objects.create(
            code="chatgpt-enterprise",
            name="ChatGPT Enterprise",
            vendor="OpenAI",
            description="Enterprise AI assistant",
            is_active=True,
        )

        self.client.force_login(self.user)

        response = self.client.get(reverse("tool_detail", kwargs={"code": tool.code}))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Review queue")

    def test_base_navigation_shows_review_link_for_reviewer(self) -> None:
        tool = AITool.objects.create(
            code="chatgpt-enterprise",
            name="ChatGPT Enterprise",
            vendor="OpenAI",
            description="Enterprise AI assistant",
            is_active=True,
        )

        reviewer_group = Group.objects.create(name="reviewer")
        self.user.groups.add(reviewer_group)

        self.client.force_login(self.user)

        response = self.client.get(reverse("tool_detail", kwargs={"code": tool.code}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Review queue")


class AIToolViewTests(TestCase):
    def setUp(self):
        user_manager = cast(UserManager, User.objects)
        self.user = user_manager.create_user(
            username="request_user",
            password="testpass123",
        )

        self.active_tool = AITool.objects.create(
            code="chatgpt-enterprise",
            name="ChatGPT Enterprise",
            vendor="OpenAI",
            description="Enterprise AI assistant",
            homepage_url="https://openai.com/chatgpt/enterprise/",
            is_active=True,
        )

        self.inactive_tool = AITool.objects.create(
            code="legacy-ai-tool",
            name="Legacy AI Tool",
            vendor="Example Vendor",
            description="Inactive legacy tool",
            homepage_url="https://example.com/legacy-ai-tool/",
            is_active=False,
        )

    def test_tool_list_requires_login(self):
        response = self.client.get(reverse("tool_list"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('tool_list')}"
        )

    def test_tool_list_shows_only_active_tools(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("tool_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ChatGPT Enterprise")
        self.assertNotContains(response, "Legacy AI Tool")

    def test_tool_detail_shows_active_tool(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("tool_detail", kwargs={"code": self.active_tool.code})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ChatGPT Enterprise")
        self.assertContains(response, "https://openai.com/chatgpt/enterprise/")

    def test_inactive_tool_detail_returns_404(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("tool_detail", kwargs={"code": self.inactive_tool.code})
        )

        self.assertEqual(response.status_code, 404)


class AccessRequestViewTests(TestCase):
    def setUp(self) -> None:
        user_manager = cast(UserManager, User.objects)
        self.user = user_manager.create_user(
            username="request_user",
            password="testpass123",
        )
        self.other_user = user_manager.create_user(
            username="other_user",
            password="testpass456",
        )

        self.active_tool = AITool.objects.create(
            code="chatgpt-enterprise",
            name="ChatGPT Enterprise",
            vendor="OpenAI",
            description="Enterprise AI assistant",
            is_active=True,
        )
        self.other_requester_tool = AITool.objects.create(
            code="other-enterprise",
            name="other Enterprise",
            vendor="Others",
            description="Enterprise AI assistant",
            is_active=True,
        )
        self.inactive_tool = AITool.objects.create(
            code="legacy-ai-tool",
            name="Legacy AI Tool",
            vendor="Example Vendor",
            description="Inactive legacy tool",
            is_active=False,
        )

    def test_request_create_requires_login(self):
        response = self.client.get(reverse("request_create"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('request_create')}",
        )

    def test_request_create_get_shows_only_active_tools(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("request_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ChatGPT Enterprise")
        self.assertNotContains(response, "Legacy AI Tool")

    def test_request_create_post_creates_pending_request(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("request_create"),
            data={
                "ai_tool": self.active_tool.pk,
                "purpose": "Pilot internal document drafting",
                "business_justification": "Needed for faster internal drafting.",
                "data_classification": "internal",
                "notes": "Department trial request.",
            },
        )

        created = AccessRequest.objects.get(
            requester=self.user, ai_tool=self.active_tool
        )
        self.assertRedirects(
            response,
            reverse("request_detail", kwargs={"pk": created.pk}),
        )
        self.assertEqual(created.status, AccessRequest.Status.PENDING)

    def test_my_request_list_shows_only_own_requests(self):
        own_request = AccessRequest.objects.create(
            requester=self.user,
            ai_tool=self.active_tool,
            purpose="Own request",
            business_justification="Own justification",
            data_classification=AccessRequest.DataClassification.INTERNAL,
        )
        other_request = AccessRequest.objects.create(
            requester=self.other_user,
            ai_tool=self.other_requester_tool,
            purpose="Other request",
            business_justification="Other justification",
            data_classification=AccessRequest.DataClassification.INTERNAL,
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("my_request_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_request.ai_tool.name)
        self.assertNotContains(response, other_request.ai_tool.name)

    def test_request_detail_is_owner_only(self):
        access_request = AccessRequest.objects.create(
            requester=self.user,
            ai_tool=self.active_tool,
            purpose="Own request",
            business_justification="Own justification",
            data_classification=AccessRequest.DataClassification.INTERNAL,
        )

        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse("request_detail", kwargs={"pk": access_request.pk})
        )

        self.assertEqual(response.status_code, 404)


class ReviewViewTests(TestCase):
    def setUp(self) -> None:
        user_manager = cast(UserManager, User.objects)

        self.reviewer = user_manager.create_user(
            username="reviewer_user",
            password="testpass123",
        )
        self.requester = user_manager.create_user(
            username="requester_user",
            password="testpass456",
        )
        self.other_requester = user_manager.create_user(
            username="other_requester",
            password="testpass789",
        )
        self.non_reviewer = user_manager.create_user(
            username="non_reviewer",
            password="testpass000",
        )

        reviewer_group = Group.objects.create(name="reviewer")
        self.reviewer.groups.add(reviewer_group)

        self.oldest_tool = AITool.objects.create(
            code="oldest-tool",
            name="Oldest Tool",
            vendor="Vendor A",
            description="Oldest pending request tool",
            is_active=True,
        )
        self.newer_tool = AITool.objects.create(
            code="newer-tool",
            name="Newer Tool",
            vendor="Vendor B",
            description="Newer pending request tool",
            is_active=True,
        )
        self.self_tool = AITool.objects.create(
            code="self-tool",
            name="Self Tool",
            vendor="Vendor C",
            description="Self-owned pending request tool",
            is_active=True,
        )
        self.reviewed_tool = AITool.objects.create(
            code="reviewed-tool",
            name="Reviewed Tool",
            vendor="Vendor D",
            description="Already reviewed request tool",
            is_active=True,
        )

        self.oldest_pending = AccessRequest.objects.create(
            requester=self.requester,
            ai_tool=self.oldest_tool,
            purpose="Oldest pending request",
            business_justification="Needs earliest review.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
        )
        self.newer_pending = AccessRequest.objects.create(
            requester=self.other_requester,
            ai_tool=self.newer_tool,
            purpose="Newer pending request",
            business_justification="Needs later review.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
        )
        self.self_owned_pending = AccessRequest.objects.create(
            requester=self.reviewer,
            ai_tool=self.self_tool,
            purpose="Reviewer self request",
            business_justification="Should not appear in queue.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
        )
        self.already_reviewed = AccessRequest.objects.create(
            requester=self.requester,
            ai_tool=self.reviewed_tool,
            purpose="Already reviewed request",
            business_justification="Should not be re-reviewed.",
            data_classification=AccessRequest.DataClassification.INTERNAL,
            notes="",
            status=AccessRequest.Status.APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
            review_comment="Already approved.",
        )

        AccessRequest.objects.filter(pk=self.oldest_pending.pk).update(
            created_at=timezone.now() - timedelta(days=2)
        )
        AccessRequest.objects.filter(pk=self.newer_pending.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        self.oldest_pending.refresh_from_db()
        self.newer_pending.refresh_from_db()

    def test_review_queue_requires_login(self) -> None:
        response = self.client.get(reverse("review_list"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('review_list')}",
        )

    def test_non_reviewer_cannot_access_review_queue(self) -> None:
        self.client.force_login(self.non_reviewer)

        response = self.client.get(reverse("review_list"))

        self.assertEqual(response.status_code, 403)

    def test_reviewer_can_access_review_queue_and_self_owned_pending_is_excluded(
        self,
    ) -> None:
        self.client.force_login(self.reviewer)

        response = self.client.get(reverse("review_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "access_requests/review_list.html")
        self.assertContains(response, "Oldest Tool")
        self.assertContains(response, "Newer Tool")
        self.assertNotContains(response, "Self Tool")
        self.assertNotContains(response, "Reviewed Tool")

        content = response.content.decode()
        self.assertLess(content.index("Oldest Tool"), content.index("Newer Tool"))

    def test_non_reviewer_cannot_access_review_detail(self) -> None:
        self.client.force_login(self.non_reviewer)

        response = self.client.get(
            reverse("review_detail", kwargs={"pk": self.oldest_pending.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_reviewer_can_access_review_detail_for_other_users_request(self) -> None:
        self.client.force_login(self.reviewer)

        response = self.client.get(
            reverse("review_detail", kwargs={"pk": self.oldest_pending.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "access_requests/review_detail.html")
        self.assertContains(response, self.requester.username)
        self.assertContains(response, "Oldest Tool")
        self.assertContains(response, "Save decision")

    def test_self_review_get_is_forbidden(self) -> None:
        self.client.force_login(self.reviewer)

        response = self.client.get(
            reverse("review_detail", kwargs={"pk": self.self_owned_pending.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_self_review_post_is_forbidden_and_request_remains_pending(self) -> None:
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse("review_detail", kwargs={"pk": self.self_owned_pending.pk}),
            data={
                "decision": "approve",
                "review_comment": "",
            },
        )

        self.assertEqual(response.status_code, 403)

        self.self_owned_pending.refresh_from_db()
        self.assertEqual(self.self_owned_pending.status, AccessRequest.Status.PENDING)
        self.assertIsNone(self.self_owned_pending.reviewed_by)
        self.assertIsNone(self.self_owned_pending.reviewed_at)

    def test_approve_post_updates_review_fields(self) -> None:
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse("review_detail", kwargs={"pk": self.oldest_pending.pk}),
            data={
                "decision": "approve",
                "review_comment": "",
            },
        )

        self.assertRedirects(
            response,
            reverse("review_detail", kwargs={"pk": self.oldest_pending.pk}),
        )

        self.oldest_pending.refresh_from_db()
        self.assertEqual(self.oldest_pending.status, AccessRequest.Status.APPROVED)
        self.assertEqual(self.oldest_pending.reviewed_by, self.reviewer)
        self.assertIsNotNone(self.oldest_pending.reviewed_at)
        self.assertEqual(self.oldest_pending.review_comment, "")

    def test_reject_without_comment_shows_form_error(self) -> None:
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse("review_detail", kwargs={"pk": self.oldest_pending.pk}),
            data={
                "decision": "reject",
                "review_comment": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "A review comment is required when rejecting a request.",
        )

        self.oldest_pending.refresh_from_db()
        self.assertEqual(self.oldest_pending.status, AccessRequest.Status.PENDING)
        self.assertIsNone(self.oldest_pending.reviewed_by)
        self.assertIsNone(self.oldest_pending.reviewed_at)

    def test_reject_with_comment_updates_review_fields(self) -> None:
        self.client.force_login(self.reviewer)

        response = self.client.post(
            reverse("review_detail", kwargs={"pk": self.newer_pending.pk}),
            data={
                "decision": "reject",
                "review_comment": "This request needs more detailed justification.",
            },
        )

        self.assertRedirects(
            response,
            reverse("review_detail", kwargs={"pk": self.newer_pending.pk}),
        )

        self.newer_pending.refresh_from_db()
        self.assertEqual(self.newer_pending.status, AccessRequest.Status.REJECTED)
        self.assertEqual(self.newer_pending.reviewed_by, self.reviewer)
        self.assertIsNotNone(self.newer_pending.reviewed_at)
        self.assertEqual(
            self.newer_pending.review_comment,
            "This request needs more detailed justification.",
        )

    def test_non_pending_request_cannot_be_reviewed_again(self) -> None:
        self.client.force_login(self.reviewer)

        original_reviewed_at = self.already_reviewed.reviewed_at
        original_comment = self.already_reviewed.review_comment

        response = self.client.post(
            reverse("review_detail", kwargs={"pk": self.already_reviewed.pk}),
            data={
                "decision": "reject",
                "review_comment": "Attempted second review.",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, "This request has already been reviewed.", status_code=400
        )

        self.already_reviewed.refresh_from_db()
        self.assertEqual(self.already_reviewed.status, AccessRequest.Status.APPROVED)
        self.assertEqual(self.already_reviewed.reviewed_by, self.reviewer)
        self.assertEqual(self.already_reviewed.reviewed_at, original_reviewed_at)
        self.assertEqual(self.already_reviewed.review_comment, original_comment)

    def test_reviewer_cannot_access_requester_facing_request_detail(self) -> None:
        self.client.force_login(self.reviewer)

        response = self.client.get(
            reverse("request_detail", kwargs={"pk": self.oldest_pending.pk})
        )

        self.assertEqual(response.status_code, 404)
