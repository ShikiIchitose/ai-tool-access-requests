from django.contrib import admin

from .models import AccessRequest, AITool


@admin.register(AITool)
class AIToolAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "vendor",
        "code",
        "is_active",
        "updated_at",
    )
    search_fields = ("name", "code", "vendor")
    list_filter = ("is_active", "vendor")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)
    fieldsets = (
        (
            "Basic information",
            {
                "fields": (
                    ("name", "code", "vendor"),
                    "description",
                    "homepage_url",
                )
            },
        ),
        (
            "Status",
            {
                "fields": ("is_active",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
    actions = ("mark_active", "mark_inactive")

    @admin.action(description="Mark selected tools as active")
    def mark_active(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Mark selected tools as inactive")
    def mark_inactive(self, request, queryset):
        queryset.update(is_active=False)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccessRequest)
class AccessRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ai_tool",
        "requester",
        "status",
        "data_classification",
        "reviewed_by",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("status", "data_classification", "created_at")
    search_fields = (
        "requester__username",
        "requester__email",
        "ai_tool__name",
        "ai_tool__code",
    )
    ordering = ("-created_at",)
    readonly_fields = (
        "requester",
        "ai_tool",
        "purpose",
        "business_justification",
        "data_classification",
        "notes",
        "status",
        "review_comment",
        "reviewed_by",
        "reviewed_at",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Request",
            {
                "fields": (
                    "requester",
                    "ai_tool",
                    "purpose",
                    "business_justification",
                    "data_classification",
                    "notes",
                )
            },
        ),
        (
            "Review",
            {
                "fields": (
                    "status",
                    "review_comment",
                    "reviewed_by",
                    "reviewed_at",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return (
            request.user.is_active
            and request.user.is_staff
            and request.user.has_perm("access_requests.view_accessrequest")
        )
