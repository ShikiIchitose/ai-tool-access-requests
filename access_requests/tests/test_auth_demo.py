from __future__ import annotations

from typing import cast

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from access_requests.models import AccessRequest, AITool

UserModel = get_user_model()


def create_demo_user(*, username: str) -> User:
    raw_user = UserModel.objects.create(
        username=username,
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    user = cast(User, raw_user)
    user.set_unusable_password()
    user.save()
    return user


@override_settings(
    ENABLE_DEMO_LOGIN=True,
    DEMO_REQUESTER_USERNAME="demo-requester",
    DEMO_REVIEWER_USERNAME="demo-reviewer",
)
class DemoLoginPageTests(TestCase):
    def test_login_page_shows_demo_buttons_when_enabled(self) -> None:
        response = self.client.get(
            reverse("login"),
            {"next": reverse("review_list")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portfolio demo access")
        self.assertContains(response, reverse("demo_login_requester"))
        self.assertContains(response, reverse("demo_login_reviewer"))
        self.assertContains(
            response,
            'name="next" value="/reviews/"',
            count=3,
        )

    @override_settings(ENABLE_DEMO_LOGIN=False)
    def test_login_page_hides_demo_buttons_when_disabled(self) -> None:
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Portfolio demo access")
        self.assertNotContains(response, reverse("demo_login_requester"))
        self.assertNotContains(response, reverse("demo_login_reviewer"))


@override_settings(
    ENABLE_DEMO_LOGIN=True,
    DEMO_REQUESTER_USERNAME="demo-requester",
    DEMO_REVIEWER_USERNAME="demo-reviewer",
)
class DemoLoginRouteTests(TestCase):
    def setUp(self) -> None:
        self.reviewer_group = Group.objects.create(name="reviewer")

        self.requester_user = create_demo_user(username="demo-requester")
        self.reviewer_user = create_demo_user(username="demo-reviewer")
        self.reviewer_user.groups.add(self.reviewer_group)

    def test_requester_demo_login_redirects_to_dashboard_by_default(self) -> None:
        response = self.client.post(reverse("demo_login_requester"))

        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            str(self.client.session["_auth_user_id"]),
            str(self.requester_user.pk),
        )

    def test_requester_demo_login_honors_safe_next(self) -> None:
        response = self.client.post(
            reverse("demo_login_requester"),
            {"next": reverse("my_request_list")},
        )

        self.assertRedirects(
            response,
            reverse("my_request_list"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            str(self.client.session["_auth_user_id"]),
            str(self.requester_user.pk),
        )

    def test_reviewer_demo_login_honors_safe_next_and_enables_reviewer_access(
        self,
    ) -> None:
        response = self.client.post(
            reverse("demo_login_reviewer"),
            {"next": reverse("review_list")},
        )

        self.assertRedirects(
            response,
            reverse("review_list"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            str(self.client.session["_auth_user_id"]),
            str(self.reviewer_user.pk),
        )

        review_response = self.client.get(reverse("review_list"))
        self.assertEqual(review_response.status_code, 200)

    def test_demo_login_ignores_unsafe_external_next_and_falls_back_to_dashboard(
        self,
    ) -> None:
        response = self.client.post(
            reverse("demo_login_requester"),
            {"next": "https://evil.example.com/phish"},
        )

        self.assertRedirects(
            response,
            reverse("dashboard"),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            str(self.client.session["_auth_user_id"]),
            str(self.requester_user.pk),
        )

    def test_demo_login_routes_reject_get(self) -> None:
        requester_response = self.client.get(reverse("demo_login_requester"))
        reviewer_response = self.client.get(reverse("demo_login_reviewer"))

        self.assertEqual(requester_response.status_code, 405)
        self.assertEqual(reviewer_response.status_code, 405)

    @override_settings(ENABLE_DEMO_LOGIN=False)
    def test_demo_login_routes_return_404_when_feature_disabled(self) -> None:
        requester_response = self.client.post(reverse("demo_login_requester"))
        reviewer_response = self.client.post(reverse("demo_login_reviewer"))

        self.assertEqual(requester_response.status_code, 404)
        self.assertEqual(reviewer_response.status_code, 404)

    @override_settings(DEMO_REQUESTER_USERNAME="missing-demo-requester")
    def test_demo_login_requester_returns_404_when_required_user_is_missing(
        self,
    ) -> None:
        response = self.client.post(reverse("demo_login_requester"))

        self.assertEqual(response.status_code, 404)

    @override_settings(DEMO_REVIEWER_USERNAME="missing-demo-reviewer")
    def test_demo_login_reviewer_returns_404_when_required_user_is_missing(
        self,
    ) -> None:
        response = self.client.post(reverse("demo_login_reviewer"))

        self.assertEqual(response.status_code, 404)


@override_settings(
    ENABLE_DEMO_LOGIN=True,
    DEMO_REQUESTER_USERNAME="demo-requester",
    DEMO_REVIEWER_USERNAME="demo-reviewer",
)
class EnsureDemoStateCommandTests(TestCase):
    def test_command_repairs_demo_user_roles_on_rerun(self) -> None:
        call_command("ensure_demo_state")

        reviewer_group = Group.objects.get(name="reviewer")
        requester_user = cast(User, UserModel.objects.get(username="demo-requester"))
        reviewer_user = cast(User, UserModel.objects.get(username="demo-reviewer"))

        requester_user.groups.add(reviewer_group)
        reviewer_user.groups.remove(reviewer_group)

        call_command("ensure_demo_state")

        requester_user.refresh_from_db()
        reviewer_user.refresh_from_db()

        self.assertFalse(requester_user.groups.filter(name="reviewer").exists())
        self.assertTrue(reviewer_user.groups.filter(name="reviewer").exists())

    def test_command_ensures_minimal_demo_seed_state(self) -> None:
        call_command("ensure_demo_state")

        reviewer_user = cast(User, UserModel.objects.get(username="demo-reviewer"))
        requester_user = cast(User, UserModel.objects.get(username="demo-requester"))

        self.assertTrue(
            UserModel.objects.filter(username="demo-seed-requester").exists()
        )

        self.assertTrue(
            AITool.objects.filter(code="chatgpt-enterprise", is_active=True).exists()
        )
        self.assertTrue(
            AITool.objects.filter(code="claude-enterprise", is_active=True).exists()
        )
        self.assertTrue(
            AITool.objects.filter(code="gemini-enterprise", is_active=True).exists()
        )

        pending_request = AccessRequest.objects.get(status=AccessRequest.Status.PENDING)
        self.assertNotEqual(pending_request.requester, reviewer_user)

        approved_request = AccessRequest.objects.get(
            status=AccessRequest.Status.APPROVED
        )
        self.assertEqual(approved_request.requester, requester_user)
        self.assertEqual(approved_request.reviewed_by, reviewer_user)

        rejected_request = AccessRequest.objects.get(
            status=AccessRequest.Status.REJECTED
        )
        self.assertEqual(rejected_request.requester, requester_user)
        self.assertEqual(rejected_request.reviewed_by, reviewer_user)
