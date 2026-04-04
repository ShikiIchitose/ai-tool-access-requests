from __future__ import annotations

from typing import Any, Final, cast

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import LoginView
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

AUTH_BACKEND_PATH: Final = "django.contrib.auth.backends.ModelBackend"
DASHBOARD_URL_NAME: Final = "dashboard"

UserModel = get_user_model()


class PortfolioLoginView(LoginView):
    template_name = "registration/login.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["enable_demo_login"] = settings.ENABLE_DEMO_LOGIN
        return context


def _get_demo_user(username: str):
    try:
        raw_user = UserModel.objects.get(username=username)
    except UserModel.DoesNotExist as exc:
        raise Http404("Demo login is not available.") from exc

    user = cast(Any, raw_user)
    if not user.is_active:
        raise Http404("Demo login is not available.")

    return raw_user


def _get_safe_redirect_target(request: HttpRequest) -> str:
    next_url = request.POST.get("next") or request.GET.get("next")

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url

    return reverse(DASHBOARD_URL_NAME)


def _demo_login(request: HttpRequest, *, username: str) -> HttpResponse:
    if not settings.ENABLE_DEMO_LOGIN:
        raise Http404("Demo login is not available.")

    user = _get_demo_user(username)
    login(request, user, backend=AUTH_BACKEND_PATH)

    return redirect(_get_safe_redirect_target(request))


@require_POST
def demo_login_requester(request: HttpRequest) -> HttpResponse:
    return _demo_login(
        request,
        username=settings.DEMO_REQUESTER_USERNAME,
    )


@require_POST
def demo_login_reviewer(request: HttpRequest) -> HttpResponse:
    return _demo_login(
        request,
        username=settings.DEMO_REVIEWER_USERNAME,
    )
