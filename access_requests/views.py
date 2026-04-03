from __future__ import annotations

from typing import cast

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, TemplateView
from django.views.generic.base import ContextMixin

from .forms import AccessRequestCreateForm, ReviewDecisionForm
from .models import AccessRequest, AITool

RequestUser = User | AnonymousUser


def is_reviewer(user: RequestUser) -> bool:
    return bool(
        user.is_authenticated
        and (user.is_superuser or user.groups.filter(name="reviewer").exists())
    )


class ReviewerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    request: HttpRequest
    permission_denied_message = "You do not have reviewer access."

    def test_func(self) -> bool:
        user = cast(RequestUser, self.request.user)
        return is_reviewer(user)

    def handle_no_permission(self) -> HttpResponseRedirect:
        user = cast(RequestUser, self.request.user)

        if not user.is_authenticated:
            return super().handle_no_permission()

        raise PermissionDenied(self.get_permission_denied_message())


class RoleContextMixin(ContextMixin):
    request: HttpRequest

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        user = cast(RequestUser, self.request.user)
        context["is_reviewer"] = is_reviewer(user)
        context["is_admin_operator"] = user.is_staff
        return context


class DashboardView(LoginRequiredMixin, RoleContextMixin, TemplateView):
    template_name = "access_requests/dashboard.html"


class AIToolListView(LoginRequiredMixin, RoleContextMixin, ListView):
    model = AITool
    template_name = "access_requests/tool_list.html"
    context_object_name = "tool_list"

    def get_queryset(self):
        return AITool.objects.filter(is_active=True)


class AIToolDetailView(LoginRequiredMixin, RoleContextMixin, DetailView):
    model = AITool
    template_name = "access_requests/tool_detail.html"
    context_object_name = "tool"
    slug_field = "code"
    slug_url_kwarg = "code"

    def get_queryset(self):
        return AITool.objects.filter(is_active=True)


class AccessRequestCreateView(LoginRequiredMixin, RoleContextMixin, CreateView):
    model = AccessRequest
    form_class = AccessRequestCreateForm
    template_name = "access_requests/request_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.requester = self.request.user

        try:
            with transaction.atomic():
                return super().form_valid(form)
        except IntegrityError:
            form.add_error(None, "A pending request for this tool already exists.")
            return self.form_invalid(form)

    def get_success_url(self) -> str:
        assert self.object is not None
        return reverse("request_detail", kwargs={"pk": self.object.pk})


class MyAccessRequestListView(LoginRequiredMixin, RoleContextMixin, ListView):
    model = AccessRequest
    template_name = "access_requests/my_request_list.html"
    context_object_name = "request_list"

    def get_queryset(self):
        return AccessRequest.objects.select_related("ai_tool", "reviewed_by").filter(
            requester=self.request.user
        )


class AccessRequestDetailView(LoginRequiredMixin, RoleContextMixin, DetailView):
    model = AccessRequest
    template_name = "access_requests/request_detail.html"
    context_object_name = "access_request"

    def get_queryset(self):
        user = self.request.user

        return AccessRequest.objects.select_related(
            "ai_tool", "requester", "reviewed_by"
        ).filter(requester=user)


class ReviewQueueListView(ReviewerRequiredMixin, RoleContextMixin, ListView):
    model = AccessRequest
    template_name = "access_requests/review_list.html"
    context_object_name = "review_queue"

    def get_queryset(self):
        user = self.request.user

        return (
            AccessRequest.objects.select_related("ai_tool", "requester")
            .filter(status=AccessRequest.Status.PENDING)
            .exclude(requester=user)
            .order_by("created_at", "id")
        )


class ReviewDetailView(ReviewerRequiredMixin, RoleContextMixin, DetailView):
    model = AccessRequest
    template_name = "access_requests/review_detail.html"
    context_object_name = "access_request"

    def get_queryset(self):
        return AccessRequest.objects.select_related(
            "ai_tool", "requester", "reviewed_by"
        )

    def get_object(self, queryset=None):
        access_request = super().get_object(queryset)

        if access_request.requester == self.request.user:
            raise PermissionDenied("You cannot review your own request.")

        return access_request

    def get_context_data(self, **kwargs: object) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        access_request = self.object

        is_pending = access_request.status == AccessRequest.Status.PENDING
        context["is_pending"] = is_pending

        if is_pending and "form" not in context:
            context["form"] = ReviewDecisionForm()

        return context

    def post(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponse:
        self.object = self.get_object()
        access_request = self.object

        if access_request.status != AccessRequest.Status.PENDING:
            context = self.get_context_data()
            context["review_error"] = "This request has already been reviewed."
            return self.render_to_response(context, status=400)

        form = ReviewDecisionForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        decision = form.cleaned_data["decision"]
        review_comment = form.cleaned_data["review_comment"]

        if decision == ReviewDecisionForm.Decision.APPROVE:
            access_request.status = AccessRequest.Status.APPROVED
        else:
            access_request.status = AccessRequest.Status.REJECTED

        access_request.review_comment = review_comment
        access_request.reviewed_by = request.user
        access_request.reviewed_at = timezone.now()

        try:
            access_request.full_clean()
        except ValidationError:
            form.add_error(
                None,
                "The review could not be saved because the request state is invalid.",
            )
            return self.render_to_response(
                self.get_context_data(form=form),
                status=400,
            )

        access_request.save(
            update_fields=[
                "status",
                "review_comment",
                "reviewed_by",
                "reviewed_at",
                "updated_at",
            ]
        )

        return redirect("review_detail", pk=access_request.pk)
