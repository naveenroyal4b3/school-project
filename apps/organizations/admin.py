from django.contrib import admin
from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = (
        "organization_code",
        "organization_name",
        "organization_type",
        "phone",
        "email",
        "subscription_plan",
        "status",
    )

    search_fields = (
        "organization_code",
        "organization_name",
        "phone",
        "email",
    )

    list_filter = (
        "organization_type",
        "subscription_plan",
        "status",
    )

    ordering = ("organization_name",)