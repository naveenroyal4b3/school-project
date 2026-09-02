"""Automatic attendance from ID-card scans.

Kept out of the views so the same logic serves the API, the Django admin and
any future offline reader sync, and so it can be tested without HTTP.
"""

import datetime

from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.notifications.services import notify_guardians

from .models import Attendance, BusAttendance, CampusScan

DEFAULT_LATE_AFTER = datetime.time(9, 15)


def _local_now():
    """Wall-clock time in the project's timezone.

    USE_TZ is on, so timezone.now() is UTC. Comparing a UTC clock against a
    school's 09:15 cutoff would mark an entire morning late, so convert first.
    """
    return timezone.localtime(timezone.now())


def status_for_arrival(student, arrived_at=None):
    """PRESENT or LATE, judged against the student's own college cutoff."""
    arrived_at = arrived_at or _local_now()

    organization = student.organization
    cutoff = getattr(organization, "late_after_time", None) or DEFAULT_LATE_AFTER

    if arrived_at.time() > cutoff:
        return Attendance.Status.LATE
    return Attendance.Status.PRESENT


@transaction.atomic
def record_campus_scan(student, scan_type, device_id=None):
    """Record a gate scan and, on the way in, mark the day's attendance.

    Returns ``(scan, attendance)``; ``attendance`` is None for an OUT scan.

    Only the first IN of the day sets the status. A student who steps out and
    scans back in after the cutoff would otherwise be downgraded from PRESENT
    to LATE by their own second scan.
    """

    now = _local_now()
    attendance = None

    if scan_type == CampusScan.ScanType.IN:
        attendance, created = Attendance.objects.get_or_create(
            student=student,
            subject=None,
            date=now.date(),
            defaults={
                "status": status_for_arrival(student, now),
                "remarks": f"Auto-marked from ID card scan at {now:%H:%M}",
                # marked_by stays null: nobody marked this, a reader did.
                "marked_by": None,
            },
        )

        if created:
            notify_guardians(
                student,
                title="Attendance recorded",
                message=(
                    f"{student.user.get_full_name() or student.user.username} "
                    f"arrived at {now:%H:%M} on {now:%d %b %Y} "
                    f"({attendance.get_status_display()})."
                ),
                notification_type=Notification.Type.ATTENDANCE,
            )

    scan = CampusScan.objects.create(
        student=student,
        scan_type=scan_type,
        device_id=device_id,
        attendance=attendance,
    )

    return scan, attendance


@transaction.atomic
def record_bus_scan(student, scan_type, bus=None, trip=None, latitude=None, longitude=None):
    """Record a bus door scan and alert the guardian."""

    record = BusAttendance.objects.create(
        student=student,
        bus=bus,
        trip=trip,
        scan_type=scan_type,
        latitude=latitude,
        longitude=longitude,
    )

    verb = "boarded" if record.scan_type == BusAttendance.ScanType.IN else "got off"
    notify_guardians(
        student,
        title="Bus attendance",
        message=(
            f"{student.user.get_full_name() or student.user.username} "
            f"{verb} the bus at {timezone.localtime(record.scanned_at):%d %b %Y %H:%M}."
        ),
        notification_type=Notification.Type.TRANSPORT,
    )

    return record
