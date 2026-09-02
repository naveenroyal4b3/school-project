from django.urls import path

from .views import (
    DailyAttendanceReportView,
    DashboardView,
    ExamReportView,
    FeeReportView,
    MonthlyAttendanceReportView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("reports/daily/", DailyAttendanceReportView.as_view(), name="report-daily"),
    path("reports/monthly/", MonthlyAttendanceReportView.as_view(), name="report-monthly"),
    path("reports/fees/", FeeReportView.as_view(), name="report-fees"),
    path("reports/exams/", ExamReportView.as_view(), name="report-exams"),
]
