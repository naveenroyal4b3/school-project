from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "admission_no",
        "roll_number",
        "user",
        "organization",
        "classroom",
        "section",
        "is_active",
    )

    search_fields = (
        "admission_no",
        "roll_number",
        "user__first_name",
        "user__last_name",
        "user__email",
        "user__phone_number",
    )

    list_filter = (
        "organization",
        "classroom",
        "section",
        "is_active",
    )