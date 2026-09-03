import datetime
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.testing import (
    make_admin,
    make_driver_user,
    make_organization,
    make_parent,
    make_student,
    make_teacher_user,
    rows,
)
from apps.notifications.models import Notification

from .models import Attendance, BusAttendance, CampusScan, StudentQRCode


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
            {"code": str(self.qr.code), "scan_type": "IN", "context": "BUS"},
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
            {"code": "not-a-real-code", "scan_type": "IN", "context": "BUS"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(BusAttendance.objects.count(), 0)

    def test_inactive_card_is_rejected(self):
        self.qr.is_active = False
        self.qr.save()

        self.client.force_authenticate(self.driver)
        response = self.client.post(
            reverse("attendance-scan"),
            {"code": str(self.qr.code), "scan_type": "IN", "context": "BUS"},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_driver_cannot_scan_another_colleges_student(self):
        other_org = make_organization("ORGB", "School B")
        other_driver = make_driver_user(other_org, "driver_b")

        self.client.force_authenticate(other_driver)
        response = self.client.post(
            reverse("attendance-scan"),
            {"code": str(self.qr.code), "scan_type": "IN", "context": "BUS"},
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(BusAttendance.objects.count(), 0)

    def test_student_may_not_scan(self):
        self.client.force_authenticate(self.student.user)
        response = self.client.post(
            reverse("attendance-scan"),
            {"code": str(self.qr.code), "scan_type": "IN", "context": "BUS"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_scan_without_a_parent_on_file_still_records(self):
        orphan = make_student(self.org, "no_parent", "ADM-2", "R-2")
        qr = StudentQRCode.objects.create(student=orphan)

        self.client.force_authenticate(self.driver)
        response = self.client.post(
            reverse("attendance-scan"),
            {"code": str(qr.code), "scan_type": "OUT", "context": "BUS"},
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
        self.assertEqual(list(rows(response)), [])


class CampusScanTests(APITestCase):
    """Scanning an ID card at the gate must mark the day's attendance without
    anyone touching a register."""

    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.parent = make_parent(self.org)
        self.student = make_student(self.org, parent=self.parent)
        self.qr = StudentQRCode.objects.create(student=self.student)
        self.admin = make_admin(self.org)

    def _scan(self, scan_type="IN", **extra):
        return self.client.post(
            reverse("attendance-scan"),
            {"code": str(self.qr.code), "scan_type": scan_type, "context": "CAMPUS", **extra},
        )

    def test_scan_marks_attendance_automatically(self):
        self.client.force_authenticate(self.admin)
        response = self._scan(device_id="GATE-1")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["context"], "CAMPUS")

        record = Attendance.objects.get()
        self.assertEqual(record.student, self.student)
        self.assertEqual(record.date, timezone.localdate())
        # Nobody marked this - a reader did.
        self.assertIsNone(record.marked_by)

        scan = CampusScan.objects.get()
        self.assertEqual(scan.device_id, "GATE-1")
        self.assertEqual(scan.attendance, record)

    def test_guardian_is_alerted_on_arrival(self):
        self.client.force_authenticate(self.admin)
        self._scan()

        notification = Notification.objects.get()
        self.assertEqual(notification.recipient, self.parent.user)
        self.assertEqual(notification.notification_type, Notification.Type.ATTENDANCE)

    def test_scanning_twice_does_not_duplicate_or_realert(self):
        self.client.force_authenticate(self.admin)
        self._scan()
        self._scan()

        self.assertEqual(Attendance.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)
        # Both scans are still logged - the event trail is append-only.
        self.assertEqual(CampusScan.objects.count(), 2)

    def test_leaving_and_returning_does_not_downgrade_to_late(self):
        """A student present at 08:00 who steps out and scans back in after the
        cutoff must stay PRESENT."""
        self.client.force_authenticate(self.admin)

        with patch("apps.attendance.services._local_now") as now:
            now.return_value = timezone.localtime().replace(hour=8, minute=0)
            self._scan("IN")
        self.assertEqual(Attendance.objects.get().status, Attendance.Status.PRESENT)

        with patch("apps.attendance.services._local_now") as now:
            now.return_value = timezone.localtime().replace(hour=11, minute=0)
            self._scan("OUT")
            self._scan("IN")

        self.assertEqual(Attendance.objects.get().status, Attendance.Status.PRESENT)

    def test_arrival_after_the_cutoff_is_marked_late(self):
        self.client.force_authenticate(self.admin)

        with patch("apps.attendance.services._local_now") as now:
            now.return_value = timezone.localtime().replace(hour=10, minute=30)
            self._scan("IN")

        self.assertEqual(Attendance.objects.get().status, Attendance.Status.LATE)

    def test_out_scan_alone_marks_nothing(self):
        self.client.force_authenticate(self.admin)
        response = self._scan("OUT")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(response.data["attendance"])
        self.assertEqual(Attendance.objects.count(), 0)

    def test_campus_scan_respects_the_colleges_own_cutoff(self):
        """Two colleges on one platform start at different hours."""
        self.org.late_after_time = datetime.time(11, 0)
        self.org.save()

        self.client.force_authenticate(self.admin)
        with patch("apps.attendance.services._local_now") as now:
            now.return_value = timezone.localtime().replace(hour=10, minute=30)
            self._scan("IN")

        # 10:30 is late against the default 09:15 but early here.
        self.assertEqual(Attendance.objects.get().status, Attendance.Status.PRESENT)

    def test_a_student_cannot_scan_themselves_in(self):
        self.client.force_authenticate(self.student.user)
        self.assertEqual(self._scan().status_code, status.HTTP_403_FORBIDDEN)


class QRCodeTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.student = make_student(self.org)
        self.admin = make_admin(self.org)

    def test_card_image_renders_a_png(self):
        qr = StudentQRCode.objects.create(student=self.student)

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("qrcode-image", args=[qr.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "image/png")
        # PNG magic number - proves it is a real image, not an error page.
        self.assertTrue(response.content.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_another_college_cannot_fetch_a_card_image(self):
        qr = StudentQRCode.objects.create(student=self.student)
        other = make_organization("ORGB", "School B")

        self.client.force_authenticate(make_admin(other, "admin_b"))
        response = self.client.get(reverse("qrcode-image", args=[qr.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_issue_all_is_idempotent(self):
        make_student(self.org, "s2", "ADM-2", "R-2")
        self.client.force_authenticate(self.admin)

        first = self.client.post(reverse("qrcode-issue-all"))
        self.assertEqual(first.data["issued"], 2)

        second = self.client.post(reverse("qrcode-issue-all"))
        self.assertEqual(second.data["issued"], 0)
        self.assertEqual(StudentQRCode.objects.count(), 2)

    def test_codes_are_unguessable(self):
        """Sequential codes would let anyone forge a scan for a student who was
        never there."""
        a = StudentQRCode.objects.create(student=self.student)
        b = StudentQRCode.objects.create(
            student=make_student(self.org, "s2", "ADM-2", "R-2")
        )

        self.assertNotEqual(a.code, b.code)
        self.assertNotIn(self.student.admission_no, str(a.code))
        self.assertGreaterEqual(len(str(a.code)), 32)


class DailyAttendanceUniquenessTests(APITestCase):
    """Daily attendance carries no subject, and a unique constraint spanning a
    nullable column is not enforced - SQL treats NULL as distinct from NULL. It
    was therefore possible to create two records for the same student and day,
    which is exactly what the gate scanner writes."""

    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.student = make_student(self.org)

    def test_a_second_daily_record_is_refused_by_the_database(self):
        Attendance.objects.create(
            student=self.student, subject=None,
            date=datetime.date(2026, 9, 3), status="PRESENT",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(
                    student=self.student, subject=None,
                    date=datetime.date(2026, 9, 3), status="ABSENT",
                )

    def test_the_same_day_for_a_different_student_is_fine(self):
        other = make_student(self.org, "s2", "ADM-2", "R-2")

        for student in (self.student, other):
            Attendance.objects.create(
                student=student, subject=None,
                date=datetime.date(2026, 9, 3), status="PRESENT",
            )

        self.assertEqual(Attendance.objects.count(), 2)

    def test_repeated_gate_scans_still_produce_one_record(self):
        """The service uses get_or_create; the constraint is the backstop for
        two scans landing at the same instant."""
        qr = StudentQRCode.objects.create(student=self.student)
        driver = make_driver_user(self.org, "driver_x")

        self.client.force_authenticate(driver)
        for _ in range(3):
            self.client.post(
                reverse("attendance-scan"),
                {"code": str(qr.code), "scan_type": "IN", "context": "CAMPUS"},
            )

        self.assertEqual(Attendance.objects.count(), 1)
