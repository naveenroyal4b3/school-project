from django.urls import path

from .views import (
    AttendancePageView,
    DashboardPageView,
    FeesPageView,
    LoginPageView,
    StudentsPageView,
    TrackingPageView,
)

urlpatterns = [
    path("", DashboardPageView.as_view(), name="page-dashboard"),
    path("login/", LoginPageView.as_view(), name="page-login"),
    path("students/", StudentsPageView.as_view(), name="page-students"),
    path("attendance/", AttendancePageView.as_view(), name="page-attendance"),
    path("tracking/", TrackingPageView.as_view(), name="page-tracking"),
    path("fees/", FeesPageView.as_view(), name="page-fees"),
]
