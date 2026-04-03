from django.urls import path

from .views import (
    AccessRequestCreateView,
    AccessRequestDetailView,
    AIToolDetailView,
    AIToolListView,
    DashboardView,
    MyAccessRequestListView,
    ReviewDetailView,
    ReviewQueueListView,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("tools/", AIToolListView.as_view(), name="tool_list"),
    path("tools/<slug:code>/", AIToolDetailView.as_view(), name="tool_detail"),
    path("requests/new/", AccessRequestCreateView.as_view(), name="request_create"),
    path("requests/mine/", MyAccessRequestListView.as_view(), name="my_request_list"),
    path(
        "requests/<int:pk>/",
        AccessRequestDetailView.as_view(),
        name="request_detail",
    ),
    path("reviews/", ReviewQueueListView.as_view(), name="review_list"),
    path("reviews/<int:pk>/", ReviewDetailView.as_view(), name="review_detail"),
]
