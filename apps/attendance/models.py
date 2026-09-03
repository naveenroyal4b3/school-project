"""Attendance Management.

Covers the document's Attendance and QR-Code Attendance tables, and both
attendance flows it describes: academic attendance marked by faculty, and
automatic bus IN/OUT recorded by scanning a student ID card.
"""

import uuid

from django.conf import settings
from django.db import models

from apps.academics.models import Subject
from apps.students.models import Student
from apps.transport.models import Bus, Trip


class Attendance(models.Model):
    """Academic attendance for one student, on one date, for one subject.

    ``subject`` is nullable so a college taking a single daily roll call can
    leave it empty; the uniqueness constraint still prevents the same student
    being marked twice for the same subject and date.
    """

    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"
        EXCUSED = "EXCUSED", "Excused"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        null=True,
        blank=True,
    )

    date = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PRESENT,
    )

    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="marked_attendance",
        null=True,
        blank=True,
    )

    remarks = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    # Mirrors subject_id, or 0 for a whole-day record. The constraint below
    # cannot span the nullable subject directly: SQL treats NULL as distinct
    # from NULL, so daily attendance - which always has subject NULL, and is
    # what the gate scanner writes - was never actually guarded. Two scans
    # landing together could each create a row for the same student and day.
    subject_key = models.PositiveIntegerField(editable=False, default=0)

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["student", "-date"])]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "subject_key", "date"],
                name="unique_attendance_per_student_subject_date",
            )
        ]

    def save(self, *args, **kwargs):
        self.subject_key = self.subject_id or 0
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"subject_key"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.admission_no} {self.date} {self.status}"


class StudentQRCode(models.Model):
    """The unique code printed on a student ID card.

    One Student -> One QR Code, per the document's relationships. The code is a
    random UUID rather than the admission number: admission numbers are
    sequential and guessable, and a guessable code would let anyone forge a
    bus scan for a student who was never on board.
    """

    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name="qr_code",
    )

    code = models.CharField(max_length=64, unique=True, default=uuid.uuid4, editable=False)

    issued_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        # Stable ordering: pagination over an unordered queryset can
        # repeat or skip rows between pages.
        ordering = ["student__admission_no"]

    def __str__(self):
        return f"QR {self.student.admission_no}"


class BusAttendance(models.Model):
    """One ID-card scan at a bus door.

    Rows are the raw event log: an IN when the student boards, an OUT when they
    get off. Pairing them into journeys is left to reporting so a missed scan
    never corrupts the record of the scans that did happen.
    """

    class ScanType(models.TextChoices):
        IN = "IN", "In"
        OUT = "OUT", "Out"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="bus_attendance",
    )

    bus = models.ForeignKey(
        Bus,
        on_delete=models.SET_NULL,
        related_name="attendance_scans",
        null=True,
        blank=True,
    )

    trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        related_name="attendance_scans",
        null=True,
        blank=True,
    )

    scan_type = models.CharField(max_length=3, choices=ScanType.choices)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scanned_at"]
        indexes = [models.Index(fields=["student", "-scanned_at"])]

    def __str__(self):
        return f"{self.student.admission_no} {self.scan_type} @ {self.scanned_at}"


class CampusScan(models.Model):
    """An ID-card scan at a campus gate or classroom reader.

    Implements the document's "Automatic IN/OUT Attendance": scanning the card
    on the way in marks the student present for the day without anyone taking a
    register.

    Like BusAttendance this is an append-only event log. The daily Attendance
    row it produces is linked back through ``attendance`` so a disputed mark can
    be traced to the exact scan, time and reader that created it.
    """

    class ScanType(models.TextChoices):
        IN = "IN", "In"
        OUT = "OUT", "Out"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="campus_scans",
    )

    scan_type = models.CharField(max_length=3, choices=ScanType.choices)

    # Which reader produced the scan - a gate, a classroom, a handheld. Free
    # text so a school can label its devices however it already does.
    device_id = models.CharField(max_length=50, blank=True, null=True)

    # The attendance row this scan created or updated, when it was an IN scan.
    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.SET_NULL,
        related_name="source_scans",
        null=True,
        blank=True,
    )

    scanned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scanned_at"]
        indexes = [models.Index(fields=["student", "-scanned_at"])]

    def __str__(self):
        return f"{self.student.admission_no} {self.scan_type} @ {self.scanned_at}"
