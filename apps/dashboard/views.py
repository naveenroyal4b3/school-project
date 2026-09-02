"""Dashboard & Reports.

Serves the document's Dashboard endpoints and its /reports/daily and
/reports/monthly attendance reports. Everything here is read-only and scoped to
the caller's organization; counts are done in the database rather than by
loading rows into Python, because these run on every dashboard load.
"""

import datetime
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from rest_framework import generics
from rest_framework.response import Response

from apps.accounts.models import User
from apps.attendance.models import Attendance, BusAttendance
from apps.examinations.models import Exam, Result
from apps.fees.models import FeePayment
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.transport.models import Bus, Driver, Route, Trip


class OrganizationFilterMixin:
    """Limit every queryset to the caller's college.

    SUPER_ADMIN sees the whole platform; a user with no organization sees
    nothing, matching the scoping rule used across the API.
    """

    def scope(self, queryset, path="organization"):
        user = self.request.user
        if user.is_superuser or user.role == User.Role.SUPER_ADMIN:
            return queryset
        if user.organization_id is None:
            return queryset.none()
        return queryset.filter(**{path: user.organization_id})


class DashboardView(OrganizationFilterMixin, generics.GenericAPIView):
    """Headline counts for the admin dashboard."""

    def get(self, request, *args, **kwargs):
        today = datetime.date.today()

        students = self.scope(Student.objects.all())
        todays_attendance = self.scope(
            Attendance.objects.filter(date=today), "student__organization"
        ).aggregate(
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            late=Count("id", filter=Q(status=Attendance.Status.LATE)),
        )

        collected = self.scope(
            FeePayment.objects.filter(status=FeePayment.Status.SUCCESS),
            "student__organization",
        ).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")

        return Response(
            {
                "students": {
                    "total": students.count(),
                    "active": students.filter(is_active=True).count(),
                },
                "faculty": self.scope(Teacher.objects.all()).count(),
                "attendance_today": todays_attendance,
                "transport": {
                    "buses": self.scope(Bus.objects.all()).count(),
                    "drivers": self.scope(Driver.objects.all()).count(),
                    "routes": self.scope(Route.objects.all()).count(),
                    "trips_in_progress": self.scope(
                        Trip.objects.filter(status=Trip.Status.IN_PROGRESS),
                        "bus__organization",
                    ).count(),
                },
                "fees": {"total_collected": collected},
                "exams": {
                    "total": self.scope(Exam.objects.all()).count(),
                    "published": self.scope(Exam.objects.filter(is_published=True)).count(),
                },
            }
        )


class DailyAttendanceReportView(OrganizationFilterMixin, generics.GenericAPIView):
    """GET /api/reports/daily/?date=YYYY-MM-DD"""

    def get(self, request, *args, **kwargs):
        raw = request.query_params.get("date")
        try:
            day = datetime.date.fromisoformat(raw) if raw else datetime.date.today()
        except ValueError:
            return Response({"error": "date must be YYYY-MM-DD."}, status=400)

        records = self.scope(
            Attendance.objects.filter(date=day), "student__organization"
        )
        summary = records.aggregate(
            present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
            absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
            late=Count("id", filter=Q(status=Attendance.Status.LATE)),
            excused=Count("id", filter=Q(status=Attendance.Status.EXCUSED)),
        )
        total = sum(summary.values())

        bus_scans = self.scope(
            BusAttendance.objects.filter(scanned_at__date=day), "student__organization"
        ).aggregate(
            boarded=Count("id", filter=Q(scan_type=BusAttendance.ScanType.IN)),
            alighted=Count("id", filter=Q(scan_type=BusAttendance.ScanType.OUT)),
        )

        return Response(
            {
                "date": day,
                "academic": summary,
                "total_marked": total,
                "attendance_rate": round(summary["present"] / total * 100, 2) if total else 0,
                "transport": bus_scans,
            }
        )


class MonthlyAttendanceReportView(OrganizationFilterMixin, generics.GenericAPIView):
    """GET /api/reports/monthly/?year=YYYY&month=M"""

    def get(self, request, *args, **kwargs):
        today = datetime.date.today()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            return Response({"error": "year and month must be integers."}, status=400)

        if not 1 <= month <= 12:
            return Response({"error": "month must be between 1 and 12."}, status=400)

        records = self.scope(
            Attendance.objects.filter(date__year=year, date__month=month),
            "student__organization",
        )

        per_student = list(
            records.values("student_id", "student__admission_no")
            .annotate(
                present=Count("id", filter=Q(status=Attendance.Status.PRESENT)),
                absent=Count("id", filter=Q(status=Attendance.Status.ABSENT)),
                total=Count("id"),
            )
            .order_by("student__admission_no")
        )

        for row in per_student:
            row["attendance_rate"] = (
                round(row["present"] / row["total"] * 100, 2) if row["total"] else 0
            )

        return Response({"year": year, "month": month, "students": per_student})


class FeeReportView(OrganizationFilterMixin, generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        payments = self.scope(FeePayment.objects.all(), "student__organization")

        by_method = list(
            payments.filter(status=FeePayment.Status.SUCCESS)
            .values("payment_method")
            .annotate(total=Sum("amount_paid"), count=Count("id"))
            .order_by("-total")
        )

        return Response(
            {
                "total_collected": payments.filter(
                    status=FeePayment.Status.SUCCESS
                ).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0"),
                "payment_count": payments.count(),
                "by_method": by_method,
                "failed": payments.filter(status=FeePayment.Status.FAILED).count(),
            }
        )


class ExamReportView(OrganizationFilterMixin, generics.GenericAPIView):
    def get(self, request, *args, **kwargs):
        results = self.scope(Result.objects.all(), "student__organization")
        total = results.count()

        return Response(
            {
                "results_recorded": total,
                "passed": results.filter(is_pass=True).count(),
                "failed": results.filter(is_pass=False).count(),
                "pass_rate": round(
                    results.filter(is_pass=True).count() / total * 100, 2
                ) if total else 0,
                "average_marks": round(
                    results.aggregate(avg=Avg("marks_obtained"))["avg"] or 0, 2
                ),
                "by_grade": list(
                    results.values("grade").annotate(count=Count("id")).order_by("grade")
                ),
            }
        )
