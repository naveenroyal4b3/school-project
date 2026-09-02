from django.urls import path

from .views import (
    AttendanceDetailView,
    AttendanceListCreateView,
    BulkAttendanceView,
    BusAttendanceListView,
    ScanView,
    StudentQRCodeDetailView,
    StudentQRCodeListCreateView,
)

urlpatterns = [
    path("", AttendanceListCreateView.as_view(), name="attendance-list"),
    path("<int:pk>/", AttendanceDetailView.as_view(), name="attendance-detail"),
    path("bulk/", BulkAttendanceView.as_view(), name="attendance-bulk"),

    path("qr-codes/", StudentQRCodeListCreateView.as_view(), name="qrcode-list"),
    path("qr-codes/<int:pk>/", StudentQRCodeDetailView.as_view(), name="qrcode-detail"),

    path("scan/", ScanView.as_view(), name="attendance-scan"),
    path("bus/", BusAttendanceListView.as_view(), name="busattendance-list"),
]
