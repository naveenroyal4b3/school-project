import datetime
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.attendance.models import Attendance
from apps.common.testing import make_admin, make_organization, make_student
from apps.fees.models import FeePayment, FeeStructure


class DashboardTests(APITestCase):
    def setUp(self):
        self.org_a = make_organization("ORGA", "School A")
        self.org_b = make_organization("ORGB", "School B")

        self.student_a = make_student(self.org_a, "s_a", "ADM-A", "R-A")
        make_student(self.org_a, "s_a2", "ADM-A2", "R-A2")
        self.student_b = make_student(self.org_b, "s_b", "ADM-B", "R-B")

        self.admin_a = make_admin(self.org_a, "admin_a")

    def test_counts_exclude_other_colleges(self):
        self.client.force_authenticate(self.admin_a)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["students"]["total"], 2)

    def test_dashboard_requires_authentication(self):
        self.assertEqual(
            self.client.get(reverse("dashboard")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class DailyReportTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.admin = make_admin(self.org)
        self.day = datetime.date(2026, 9, 2)

        for i, outcome in enumerate(["PRESENT", "PRESENT", "ABSENT", "LATE"]):
            student = make_student(self.org, f"s{i}", f"ADM-{i}", f"R-{i}")
            Attendance.objects.create(student=student, date=self.day, status=outcome)

    def test_daily_report_computes_the_attendance_rate(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("report-daily"), {"date": "2026-09-02"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["academic"]["present"], 2)
        self.assertEqual(response.data["academic"]["absent"], 1)
        self.assertEqual(response.data["total_marked"], 4)
        self.assertEqual(response.data["attendance_rate"], 50.0)

    def test_a_day_with_no_records_does_not_divide_by_zero(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("report-daily"), {"date": "2026-01-01"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["attendance_rate"], 0)

    def test_a_malformed_date_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("report-daily"), {"date": "02-09-2026"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class MonthlyReportTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.admin = make_admin(self.org)
        self.student = make_student(self.org)

        for day, outcome in [(1, "PRESENT"), (2, "PRESENT"), (3, "ABSENT"), (4, "PRESENT")]:
            Attendance.objects.create(
                student=self.student, date=datetime.date(2026, 9, day), status=outcome
            )

    def test_monthly_report_summarises_per_student(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("report-monthly"), {"year": 2026, "month": 9})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data["students"][0]
        self.assertEqual(row["present"], 3)
        self.assertEqual(row["absent"], 1)
        self.assertEqual(row["attendance_rate"], 75.0)

    def test_an_out_of_range_month_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("report-monthly"), {"year": 2026, "month": 13})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class FeeReportTests(APITestCase):
    def test_report_counts_only_successful_payments_in_the_total(self):
        org = make_organization("ORGA", "School A")
        student = make_student(org)
        fee = FeeStructure.objects.create(
            organization=org,
            name="Tuition",
            amount=Decimal("1000.00"),
            due_date=datetime.date(2026, 12, 31),
        )

        FeePayment.objects.create(
            student=student, fee_structure=fee, amount_paid=Decimal("600.00")
        )
        FeePayment.objects.create(
            student=student,
            fee_structure=fee,
            amount_paid=Decimal("400.00"),
            status=FeePayment.Status.FAILED,
        )

        self.client.force_authenticate(make_admin(org))
        response = self.client.get(reverse("report-fees"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_collected"], Decimal("600.00"))
        self.assertEqual(response.data["payment_count"], 2)
        self.assertEqual(response.data["failed"], 1)
