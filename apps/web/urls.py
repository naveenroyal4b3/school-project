from django.urls import path

from .views import (
    AttendancePageView,
    DashboardPageView,
    FeesPageView,
    IDCardPageView,
    LoginPageView,
    ResultsPageView,
    ScannerPageView,
    StudentsPageView,
    TrackingPageView,
)

urlpatterns = [
    path("", DashboardPageView.as_view(), name="page-dashboard"),
    path("login/", LoginPageView.as_view(), name="page-login"),
    path("students/", StudentsPageView.as_view(), name="page-students"),
    path("attendance/", AttendancePageView.as_view(), name="page-attendance"),
    path("scanner/", ScannerPageView.as_view(), name="page-scanner"),
    path("id-cards/", IDCardPageView.as_view(), name="page-id-cards"),
    path("tracking/", TrackingPageView.as_view(), name="page-tracking"),
    path("fees/", FeesPageView.as_view(), name="page-fees"),
    path("results/", ResultsPageView.as_view(), name="page-results"),
]
