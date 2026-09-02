from django.contrib import admin

from .models import Exam, ExamSchedule, Result


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ("name", "exam_type", "start_date", "end_date", "is_published")
    list_filter = ("exam_type", "is_published")


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ("student", "exam_schedule", "marks_obtained", "grade", "is_pass")
    list_filter = ("grade", "is_pass")


admin.site.register(ExamSchedule)
