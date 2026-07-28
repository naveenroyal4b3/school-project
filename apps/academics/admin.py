from django.contrib import admin
from .models import AcademicYear, ClassRoom, Section, Subject


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "start_date",
        "end_date",
        "is_active",
    )
    list_filter = (
        "organization",
        "is_active",
    )
    search_fields = (
        "name",
    )


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "academic_year",
        "is_active",
    )
    list_filter = (
        "academic_year",
        "is_active",
    )
    search_fields = (
        "name",
    )


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "classroom",
        "capacity",
        "is_active",
    )
    list_filter = (
        "classroom",
        "is_active",
    )
    search_fields = (
        "name",
    )


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "classroom",
        "is_active",
    )
    list_filter = (
        "classroom",
        "is_active",
    )
    search_fields = (
        "name",
        "code",
    )