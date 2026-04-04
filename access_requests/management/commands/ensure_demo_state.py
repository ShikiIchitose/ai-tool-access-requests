from __future__ import annotations

from typing import cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from access_requests.models import AccessRequest, AITool


class Command(BaseCommand):
    help = "Ensure portfolio demo users, roles, tools, and seeded request state."

    REVIEWER_GROUP_NAME = "reviewer"
    AUXILIARY_REQUESTER_USERNAME = "demo-seed-requester"

    TOOL_SEEDS = (
        {
            "code": "chatgpt-enterprise",
            "name": "ChatGPT Enterprise",
            "vendor": "OpenAI",
            "description": (
                "Enterprise conversational AI for drafting, analysis, and internal productivity."
            ),
            "homepage_url": "https://openai.com/chatgpt/enterprise/",
        },
        {
            "code": "claude-enterprise",
            "name": "Claude Enterprise",
            "vendor": "Anthropic",
            "description": (
                "Enterprise AI assistant for writing, analysis, and document-based workflows."
            ),
            "homepage_url": "https://www.anthropic.com/claude/enterprise",
        },
        {
            "code": "gemini-enterprise",
            "name": "Gemini Enterprise",
            "vendor": "Google",
            "description": (
                "Enterprise generative AI for research, summarization, and workspace productivity."
            ),
            "homepage_url": "https://workspace.google.com/solutions/ai/",
        },
    )

    def handle(self, *args: object, **options: object) -> None:
        with transaction.atomic():
            reviewer_group = self._ensure_reviewer_group()

            requester_user = self._ensure_public_demo_user(
                username=settings.DEMO_REQUESTER_USERNAME
            )
            reviewer_user = self._ensure_public_demo_user(
                username=settings.DEMO_REVIEWER_USERNAME
            )
            seed_requester = self._ensure_auxiliary_requester()

            self._repair_demo_roles(
                requester_user=requester_user,
                reviewer_user=reviewer_user,
                reviewer_group=reviewer_group,
            )

            tools = self._ensure_tools()

            self._ensure_seed_requests(
                requester_user=requester_user,
                reviewer_user=reviewer_user,
                seed_requester=seed_requester,
                tools=tools,
            )

        self.stdout.write(self.style.SUCCESS("Demo state ensured successfully."))

    def _ensure_reviewer_group(self) -> Group:
        group, created = Group.objects.get_or_create(name=self.REVIEWER_GROUP_NAME)
        if created:
            self.stdout.write(self.style.SUCCESS("Created reviewer group."))
        else:
            self.stdout.write("Reviewer group already exists.")
        return group

    def _ensure_public_demo_user(self, username: str) -> User:
        user_model = get_user_model()
        raw_user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
            },
        )
        user = cast(User, raw_user)

        changed = False

        if not user.is_active:
            user.is_active = True
            changed = True

        if user.is_staff:
            user.is_staff = False
            changed = True

        if user.is_superuser:
            user.is_superuser = False
            changed = True

        if user.has_usable_password():
            user.set_unusable_password()
            changed = True

        if created or changed:
            user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created public demo user: {username}")
            )
        elif changed:
            self.stdout.write(
                self.style.SUCCESS(f"Updated public demo user: {username}")
            )
        else:
            self.stdout.write(f"Public demo user already valid: {username}")

        return user

    def _ensure_auxiliary_requester(self) -> User:
        user_model = get_user_model()
        raw_user, created = user_model.objects.get_or_create(
            username=self.AUXILIARY_REQUESTER_USERNAME,
            defaults={
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
            },
        )
        user = cast(User, raw_user)

        changed = False

        if not user.is_active:
            user.is_active = True
            changed = True

        if user.is_staff:
            user.is_staff = False
            changed = True

        if user.is_superuser:
            user.is_superuser = False
            changed = True

        if user.has_usable_password():
            user.set_unusable_password()
            changed = True

        if changed or created:
            user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created auxiliary seed requester: {self.AUXILIARY_REQUESTER_USERNAME}"
                )
            )
        elif changed:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated auxiliary seed requester: {self.AUXILIARY_REQUESTER_USERNAME}"
                )
            )
        else:
            self.stdout.write(
                f"Auxiliary seed requester already valid: {self.AUXILIARY_REQUESTER_USERNAME}"
            )

        return user

    def _repair_demo_roles(
        self,
        *,
        requester_user: User,
        reviewer_user: User,
        reviewer_group: Group,
    ) -> None:
        if requester_user.groups.filter(name=reviewer_group.name).exists():
            requester_user.groups.remove(reviewer_group)
            self.stdout.write(
                self.style.SUCCESS("Removed requester demo user from reviewer group.")
            )
        else:
            self.stdout.write("Requester demo user is not in reviewer group.")

        if not reviewer_user.groups.filter(name=reviewer_group.name).exists():
            reviewer_user.groups.add(reviewer_group)
            self.stdout.write(
                self.style.SUCCESS("Added reviewer demo user to reviewer group.")
            )
        else:
            self.stdout.write("Reviewer demo user already in reviewer group.")

    def _ensure_tools(self) -> dict[str, AITool]:
        tools: dict[str, AITool] = {}

        for seed in self.TOOL_SEEDS:
            tool, created = AITool.objects.update_or_create(
                code=seed["code"],
                defaults={
                    "name": seed["name"],
                    "vendor": seed["vendor"],
                    "description": seed["description"],
                    "homepage_url": seed["homepage_url"],
                    "is_active": True,
                },
            )
            tools[tool.code] = tool

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created active tool seed: {tool.code}")
                )
            else:
                self.stdout.write(f"Ensured active tool seed: {tool.code}")

        return tools

    def _ensure_seed_requests(
        self,
        *,
        requester_user: User,
        reviewer_user: User,
        seed_requester: User,
        tools: dict[str, AITool],
    ) -> None:
        now = timezone.now()

        pending_request, pending_created = AccessRequest.objects.get_or_create(
            requester=seed_requester,
            ai_tool=tools["chatgpt-enterprise"],
            status=AccessRequest.Status.PENDING,
            purpose="Evaluate enterprise chat assistant for internal documentation drafting",
            defaults={
                "business_justification": (
                    "Need a reviewable pending example for the public reviewer demo flow."
                ),
                "data_classification": AccessRequest.DataClassification.INTERNAL,
                "notes": "Seeded pending request for reviewer queue evaluation.",
                "review_comment": "",
                "reviewed_by": None,
                "reviewed_at": None,
            },
        )
        if pending_created:
            self.stdout.write(self.style.SUCCESS("Created seeded pending request."))
        else:
            updated = False
            if pending_request.reviewed_by is not None:
                pending_request.reviewed_by = None
                updated = True
            if pending_request.reviewed_at is not None:
                pending_request.reviewed_at = None
                updated = True
            if pending_request.review_comment != "":
                pending_request.review_comment = ""
                updated = True
            if (
                pending_request.data_classification
                != AccessRequest.DataClassification.INTERNAL
            ):
                pending_request.data_classification = (
                    AccessRequest.DataClassification.INTERNAL
                )
                updated = True
            if (
                pending_request.notes
                != "Seeded pending request for reviewer queue evaluation."
            ):
                pending_request.notes = (
                    "Seeded pending request for reviewer queue evaluation."
                )
                updated = True
            if pending_request.business_justification != (
                "Need a reviewable pending example for the public reviewer demo flow."
            ):
                pending_request.business_justification = "Need a reviewable pending example for the public reviewer demo flow."
                updated = True

            if updated:
                pending_request.full_clean()
                pending_request.save()
                self.stdout.write(
                    self.style.SUCCESS("Repaired seeded pending request.")
                )
            else:
                self.stdout.write("Seeded pending request already valid.")

        approved_request, approved_created = AccessRequest.objects.get_or_create(
            requester=requester_user,
            ai_tool=tools["claude-enterprise"],
            status=AccessRequest.Status.APPROVED,
            purpose="Use an enterprise writing assistant for policy drafting support",
            defaults={
                "business_justification": (
                    "Need an approved example in the public demo dataset."
                ),
                "data_classification": AccessRequest.DataClassification.INTERNAL,
                "notes": "Seeded approved request for demo state coverage.",
                "review_comment": "Approved for internal knowledge-work use.",
                "reviewed_by": reviewer_user,
                "reviewed_at": now,
            },
        )
        if approved_created:
            self.stdout.write(self.style.SUCCESS("Created seeded approved request."))
        else:
            updated = False
            if approved_request.reviewed_by != reviewer_user:
                approved_request.reviewed_by = reviewer_user
                updated = True
            if approved_request.reviewed_at is None:
                approved_request.reviewed_at = now
                updated = True
            if (
                approved_request.review_comment
                != "Approved for internal knowledge-work use."
            ):
                approved_request.review_comment = (
                    "Approved for internal knowledge-work use."
                )
                updated = True
            if (
                approved_request.data_classification
                != AccessRequest.DataClassification.INTERNAL
            ):
                approved_request.data_classification = (
                    AccessRequest.DataClassification.INTERNAL
                )
                updated = True
            if (
                approved_request.notes
                != "Seeded approved request for demo state coverage."
            ):
                approved_request.notes = (
                    "Seeded approved request for demo state coverage."
                )
                updated = True
            if approved_request.business_justification != (
                "Need an approved example in the public demo dataset."
            ):
                approved_request.business_justification = (
                    "Need an approved example in the public demo dataset."
                )
                updated = True

            if updated:
                approved_request.full_clean()
                approved_request.save()
                self.stdout.write(
                    self.style.SUCCESS("Repaired seeded approved request.")
                )
            else:
                self.stdout.write("Seeded approved request already valid.")

        rejected_request, rejected_created = AccessRequest.objects.get_or_create(
            requester=requester_user,
            ai_tool=tools["gemini-enterprise"],
            status=AccessRequest.Status.REJECTED,
            purpose="Use a workspace AI assistant with confidential project materials",
            defaults={
                "business_justification": (
                    "Need a rejected example in the public demo dataset."
                ),
                "data_classification": AccessRequest.DataClassification.CONFIDENTIAL,
                "notes": "Seeded rejected request for demo state coverage.",
                "review_comment": (
                    "Rejected because confidential project data is not approved for this tool."
                ),
                "reviewed_by": reviewer_user,
                "reviewed_at": now,
            },
        )
        if rejected_created:
            self.stdout.write(self.style.SUCCESS("Created seeded rejected request."))
        else:
            updated = False
            if rejected_request.reviewed_by != reviewer_user:
                rejected_request.reviewed_by = reviewer_user
                updated = True
            if rejected_request.reviewed_at is None:
                rejected_request.reviewed_at = now
                updated = True
            if rejected_request.review_comment != (
                "Rejected because confidential project data is not approved for this tool."
            ):
                rejected_request.review_comment = "Rejected because confidential project data is not approved for this tool."
                updated = True
            if (
                rejected_request.data_classification
                != AccessRequest.DataClassification.CONFIDENTIAL
            ):
                rejected_request.data_classification = (
                    AccessRequest.DataClassification.CONFIDENTIAL
                )
                updated = True
            if (
                rejected_request.notes
                != "Seeded rejected request for demo state coverage."
            ):
                rejected_request.notes = (
                    "Seeded rejected request for demo state coverage."
                )
                updated = True
            if rejected_request.business_justification != (
                "Need a rejected example in the public demo dataset."
            ):
                rejected_request.business_justification = (
                    "Need a rejected example in the public demo dataset."
                )
                updated = True

            if updated:
                rejected_request.full_clean()
                rejected_request.save()
                self.stdout.write(
                    self.style.SUCCESS("Repaired seeded rejected request.")
                )
            else:
                self.stdout.write("Seeded rejected request already valid.")
