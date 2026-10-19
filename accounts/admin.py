from django.contrib import admin

from .models import PendingSignup


@admin.register(PendingSignup)
class PendingSignupAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "email",
        "created_at",
        "updated_at",
    )
    search_fields = ("username", "email")
    list_filter = ("created_at", "updated_at")
    ordering = ("-updated_at",)
    readonly_fields = ("created_at", "updated_at")

    exclude = ("password_hash",)

    def has_add_permission(self, request):
        return False