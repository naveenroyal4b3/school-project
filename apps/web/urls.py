from apps.fees.pages import receipt_page
from django.urls import path

from .views import (
    AttendancePageView,
    DashboardPageView,
    FeesPageView,
    IDCardPageView,
    LoginPageView,
    NotificationsPageView,
    ResultsPageView,
    ScannerPageView,
    StudentsPageView,
    TeachersPageView,
    TimetablePageView,
    TrackingPageView,
    TransportPageView,
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
    path("teachers/", TeachersPageView.as_view(), name="page-teachers"),
    path("transport/", TransportPageView.as_view(), name="page-transport"),
    path("timetable/", TimetablePageView.as_view(), name="page-timetable"),
    path("notifications/", NotificationsPageView.as_view(), name="page-notifications"),
    path("receipts/<int:pk>/", receipt_page, name="page-receipt"),
]
