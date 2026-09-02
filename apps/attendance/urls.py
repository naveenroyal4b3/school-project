from django.urls import path

from .views import (
    AttendanceDetailView,
    AttendanceListCreateView,
    BulkAttendanceView,
    BusAttendanceListView,
    CampusScanListView,
    IssueQRCodesView,
    ScanView,
    StudentQRCodeDetailView,
    StudentQRCodeImageView,
    StudentQRCodeListCreateView,
)

urlpatterns = [
    path("", AttendanceListCreateView.as_view(), name="attendance-list"),
    path("<int:pk>/", AttendanceDetailView.as_view(), name="attendance-detail"),
    path("bulk/", BulkAttendanceView.as_view(), name="attendance-bulk"),

    path("qr-codes/", StudentQRCodeListCreateView.as_view(), name="qrcode-list"),
    path("qr-codes/issue-all/", IssueQRCodesView.as_view(), name="qrcode-issue-all"),
    path("qr-codes/<int:pk>/", StudentQRCodeDetailView.as_view(), name="qrcode-detail"),
    path("qr-codes/<int:pk>/image/", StudentQRCodeImageView.as_view(), name="qrcode-image"),

    path("scan/", ScanView.as_view(), name="attendance-scan"),
    path("bus/", BusAttendanceListView.as_view(), name="busattendance-list"),
    path("campus/", CampusScanListView.as_view(), name="campusscan-list"),
]
