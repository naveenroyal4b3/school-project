from django.urls import path

from .views import (
    ExamDetailView,
    ExamListCreateView,
    ExamScheduleDetailView,
    ExamScheduleListCreateView,
    PublishResultsView,
    ResultDetailView,
    ResultListCreateView,
    StudentPerformanceView,
)

urlpatterns = [
    path("", ExamListCreateView.as_view(), name="exam-list"),
    path("<int:pk>/", ExamDetailView.as_view(), name="exam-detail"),
    path("<int:pk>/publish/", PublishResultsView.as_view(), name="exam-publish"),

    path("schedules/", ExamScheduleListCreateView.as_view(), name="examschedule-list"),
    path("schedules/<int:pk>/", ExamScheduleDetailView.as_view(), name="examschedule-detail"),

    path("results/", ResultListCreateView.as_view(), name="result-list"),
    path("results/<int:pk>/", ResultDetailView.as_view(), name="result-detail"),

    path("performance/<int:student_id>/", StudentPerformanceView.as_view(), name="student-performance"),
]
