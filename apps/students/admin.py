from django.contrib import admin
from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "admission_no",
        "first_name",
        "last_name",
        "email",
        "phone",
        "gender",
    )

    search_fields = (
        "admission_no",
        "first_name",
        "last_name",
        "email",
    )

    list_filter = (
        "gender",
    )

    ordering = ("admission_no",)