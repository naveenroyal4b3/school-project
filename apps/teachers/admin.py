from django.contrib import admin
from .models import Teacher


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "user",
        "organization",
        "qualification",
        "experience",
        "is_active",
    )

    search_fields = (
        "employee_id",
        "user__first_name",
        "user__last_name",
        "user__email",
        "user__phone_number",
    )

    list_filter = (
        "organization",
        "is_active",
    )