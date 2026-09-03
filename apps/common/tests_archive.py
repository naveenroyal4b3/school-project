"""Archiving.

Deleting a student used to cascade away their attendance, fee payments and exam
results — exactly the records a school needs years later for a transcript or a
disputed fee.
"""

import datetime
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.fees.models import FeePayment, FeeStructure
from apps.students.models import Student

from .testing import make_admin, make_organization, make_student, make_user, rows


class ArchiveTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.admin = make_admin(self.org)
        self.student = make_student(self.org, "s1", "ADM-1", "R-1")

        Attendance.objects.create(
            student=self.student, date=datetime.date(2026, 9, 1), status="PRESENT"
        )
        fee = FeeStructure.objects.create(
            organization=self.org, name="Tuition",
            amount=Decimal("1000.00"), due_date=datetime.date(2026, 12, 31),
        )
        FeePayment.objects.create(
            student=self.student, fee_structure=fee, amount_paid=Decimal("1000.00")
        )

        self.client.force_authenticate(self.admin)

    def test_deleting_archives_rather_than_destroys(self):
        response = self.client.delete(reverse("student-detail", args=[self.student.id]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Student.objects.count(), 0)          # hidden
        self.assertEqual(Student.all_objects.count(), 1)      # kept

    def test_the_history_survives(self):
        """The whole point: a leaver's payment record must remain."""
        self.client.delete(reverse("student-detail", args=[self.student.id]))

        self.assertEqual(Attendance.objects.filter(student=self.student).count(), 1)
        self.assertEqual(FeePayment.objects.filter(student=self.student).count(), 1)

    def test_an_archived_student_leaves_the_list(self):
        self.client.delete(reverse("student-detail", args=[self.student.id]))

        response = self.client.get(reverse("student-list"))
        self.assertEqual(rows(response), [])

    def test_archived_students_can_be_listed_deliberately(self):
        self.client.delete(reverse("student-detail", args=[self.student.id]))

        response = self.client.get(reverse("student-list"), {"archived": "true"})
        self.assertEqual([r["admission_no"] for r in rows(response)], ["ADM-1"])

    def test_an_archived_student_can_be_restored(self):
        self.student.archive()
        self.assertEqual(Student.objects.count(), 0)

        self.student.restore()
        self.assertEqual(Student.objects.count(), 1)

    def test_archiving_twice_keeps_the_original_timestamp(self):
        self.student.archive()
        first = self.student.archived_at

        self.student.archive()
        self.student.refresh_from_db()
        self.assertEqual(self.student.archived_at, first)

    def test_an_org_admin_cannot_erase_permanently(self):
        """A mistaken click must not be able to destroy a payment history."""
        self.client.delete(
            reverse("student-detail", args=[self.student.id]) + "?hard=true"
        )

        self.assertEqual(Student.all_objects.count(), 1)

    def test_a_platform_superuser_can_erase_permanently(self):
        """Kept available for a genuine erasure request."""
        root = make_user("root", User.Role.SUPER_ADMIN, self.org)
        root.is_superuser = True
        root.save()

        self.client.force_authenticate(root)
        self.client.delete(
            reverse("student-detail", args=[self.student.id]) + "?hard=true"
        )

        self.assertEqual(Student.all_objects.count(), 0)
