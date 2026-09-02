import datetime

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.testing import (
    make_admin,
    make_driver_user,
    make_organization,
    make_parent,
    make_student,
    make_teacher_user,
)
from apps.notifications.models import Notification

from .models import Attendance, BusAttendance, StudentQRCode


class ScanTests(APITestCase):
    """The ID-card scan is the highest-risk endpoint: it writes attendance and
    messages a guardian, driven only by a scanned code."""

    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.parent = make_parent(self.org)
        self.student = make_student(self.org, parent=self.parent)
        self.qr = StudentQRCode.objects.create(student=self.student)
        self.driver = make_driver_user(self.org)

    def test_scan_records_attendance_and_alerts_the_guardian(self):
        self.client.force_authenticate(self.driver)

        response = self.client.post(
            reverse("attendance-scan"),
            {"code": str(self.qr.code), "scan_type": "IN"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BusAttendance.objects.count(), 1)

        notification = Notification.objects.get()
        self.assertEqual(notification.recipient, self.parent.user)
        self.assertEqual(notification.notification_type, Notification.Type.TRANSPORT)
        self.assertEqual(notification.status, Notification.Status.SENT)

    def test_unknown_code_is_rejected(self):
        self.client.force_authenticate(self.driver)
        response = self.client.post(
            reverse("attendance-scan"),
            {"code": "not-a-real-code", "scan_type": "IN"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(BusAttendance.objects.count(), 0)

    def test_inactive_card_is_rejected(self):
        self.qr.is_active = False
        self.qr.save()

        self.client.force_authenticate(self.driver)
        response = self.client.post(
            reverse("attendance-scan"),
            {"code": str(self.qr.code), "scan_type": "IN"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_driver_cannot_scan_another_colleges_student(self):
        other_org = make_organization("ORGB", "School B")
        other_driver = make_driver_user(other_org, "driver_b")

        self.client.force_authenticate(other_driver)
        response = self.client.post(
            reverse("attendance-scan"),
            {"code": str(self.qr.code), "scan_type": "IN"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(BusAttendance.objects.count(), 0)

    def test_student_may_not_scan(self):
        self.client.force_authenticate(self.student.user)
        response = self.client.post(
            reverse("attendance-scan"),
            {"code": str(self.qr.code), "scan_type": "IN"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_scan_without_a_parent_on_file_still_records(self):
        orphan = make_student(self.org, "no_parent", "ADM-2", "R-2")
        qr = StudentQRCode.objects.create(student=orphan)

        self.client.force_authenticate(self.driver)
        response = self.client.post(
            reverse("attendance-scan"), {"code": str(qr.code), "scan_type": "OUT"}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Notification.objects.count(), 0)


class BulkAttendanceTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.teacher = make_teacher_user(self.org)
        self.a = make_student(self.org, "s_a", "ADM-A", "R-A")
        self.b = make_student(self.org, "s_b", "ADM-B", "R-B")

    def test_marks_a_whole_class(self):
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            reverse("attendance-bulk"),
            {
                "date": "2026-09-02",
                "records": [
                    {"student": self.a.id, "status": "PRESENT"},
                    {"student": self.b.id, "status": "ABSENT"},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Attendance.objects.count(), 2)
        self.assertEqual(
            Attendance.objects.get(student=self.b).status, Attendance.Status.ABSENT
        )

    def test_an_unknown_student_rolls_back_the_whole_batch(self):
        self.client.force_authenticate(self.teacher)

        response = self.client.post(
            reverse("attendance-bulk"),
            {
                "date": "2026-09-02",
                "records": [
                    {"student": self.a.id, "status": "PRESENT"},
                    {"student": 999999, "status": "PRESENT"},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_marked_by_is_recorded_from_the_session_not_the_payload(self):
        self.client.force_authenticate(self.teacher)
        impostor = make_admin(self.org, "impostor")

        self.client.post(
            reverse("attendance-list"),
            {
                "student": self.a.id,
                "date": "2026-09-03",
                "status": "PRESENT",
                "marked_by": impostor.id,
            },
        )

        self.assertEqual(Attendance.objects.get().marked_by, self.teacher)


class AttendanceScopingTests(APITestCase):
    def test_attendance_is_scoped_to_the_callers_college(self):
        org_a = make_organization("ORGA", "School A")
        org_b = make_organization("ORGB", "School B")

        student_b = make_student(org_b, "s_b", "ADM-B", "R-B")
        Attendance.objects.create(
            student=student_b, date=datetime.date(2026, 9, 2), status="PRESENT"
        )

        self.client.force_authenticate(make_admin(org_a, "admin_a"))
        response = self.client.get(reverse("attendance-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data), [])
