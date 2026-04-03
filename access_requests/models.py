from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class AITool(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    vendor = models.CharField(max_length=100)
    description = models.TextField()
    homepage_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return f"{self.name} [{self.code}]"


class AccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class DataClassification(models.TextChoices):
        PUBLIC = "public", "Public"
        INTERNAL = "internal", "Internal"
        CONFIDENTIAL = "confidential", "Confidential"
        PERSONAL_DATA = "personal_data", "Personal data"

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="access_requests",
    )
    ai_tool = models.ForeignKey(
        AITool,
        on_delete=models.PROTECT,
        related_name="access_requests",
    )
    purpose = models.CharField(max_length=200)
    business_justification = models.TextField()
    data_classification = models.CharField(
        max_length=20,
        choices=DataClassification.choices,
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    review_comment = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reviewed_access_requests",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "ai_tool"],
                condition=Q(status="pending"),
                name="uniq_pending_request_per_user_tool",
            )
        ]

    def clean(self) -> None:
        errors: dict[str, str] = {}

        if self.status == self.Status.PENDING:
            if self.reviewed_by is not None:
                errors["reviewed_by"] = "Pending requests must not have a reviewer."
            if self.reviewed_at is not None:
                errors["reviewed_at"] = (
                    "Pending requests must not have a review timestamp."
                )

        elif self.status in {self.Status.APPROVED, self.Status.REJECTED}:
            if self.reviewed_by is None:
                errors["reviewed_by"] = "Reviewed requests must have a reviewer."
            if self.reviewed_at is None:
                errors["reviewed_at"] = (
                    "Reviewed requests must have a review timestamp."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.requester} -> {self.ai_tool} ({self.status})"
