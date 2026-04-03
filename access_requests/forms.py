from __future__ import annotations

from typing import Any, cast

from django import forms
from django.db import models

from .models import AccessRequest, AITool


class AccessRequestCreateForm(forms.ModelForm):
    class Meta:
        model = AccessRequest
        fields = (
            "ai_tool",
            "purpose",
            "business_justification",
            "data_classification",
            "notes",
        )
        widgets = {
            "business_justification": forms.Textarea(attrs={"rows": 5}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args: Any, user, **kwargs: Any) -> None:
        self.user = user
        super().__init__(*args, **kwargs)

        queryset = AITool.objects.filter(is_active=True)
        if self.is_bound:
            queryset = AITool.objects.all()

        ai_tool_field = cast(forms.ModelChoiceField, self.fields["ai_tool"])
        ai_tool_field.queryset = queryset.order_by("name", "id")

    def clean_ai_tool(self) -> AITool:
        ai_tool = self.cleaned_data["ai_tool"]

        if not ai_tool.is_active:
            raise forms.ValidationError(
                "This tool is inactive and cannot accept new requests."
            )

        return ai_tool

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        ai_tool: AITool | None = cleaned_data.get("ai_tool")

        if ai_tool is None:
            return cleaned_data

        if not getattr(self.user, "is_authenticated", False):
            return cleaned_data

        duplicate_exists = AccessRequest.objects.filter(
            requester=self.user,
            ai_tool=ai_tool,
            status=AccessRequest.Status.PENDING,
        ).exists()

        if duplicate_exists:
            raise forms.ValidationError(
                "A pending request for this tool already exists."
            )

        return cleaned_data


class ReviewDecisionForm(forms.Form):
    class Decision(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"

    decision = forms.ChoiceField(choices=Decision.choices)
    review_comment = forms.CharField(
        required=False,
        strip=True,
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        decision = cleaned_data.get("decision")
        review_comment = cleaned_data.get("review_comment", "")

        if decision == self.Decision.REJECT and not review_comment:
            self.add_error(
                "review_comment",
                "A review comment is required when rejecting a request.",
            )

        return cleaned_data
