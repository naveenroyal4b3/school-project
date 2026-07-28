from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    list_display = (
        "username",
        "email",
        "phone_number",
        "role",
        "organization",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "role",
        "organization",
        "is_active",
        "is_staff",
    )

    search_fields = (
        "username",
        "email",
        "phone_number",
    )

    ordering = ("username",)

    fieldsets = UserAdmin.fieldsets + (
        (
            "SSMS Information",
            {
                "fields": (
                    "role",
                    "organization",
                    "phone_number",
                    "profile_image",
                )
            },
        ),
    )