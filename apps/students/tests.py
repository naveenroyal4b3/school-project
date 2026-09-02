"""Student creation.

Adding a student creates their sign-in account in the same request. Before
this, ``user`` was a required foreign key with no endpoint listing the accounts
to choose from, so the form could never be submitted.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.testing import make_admin, make_organization, make_student, rows

from .models import Student


class StudentCreationTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.admin = make_admin(self.org)
        self.client.force_authenticate(self.admin)

    def payload(self, **extra):
        data = {
            "new_username": "arjun.s",
            "first_name": "Arjun",
            "last_name": "Sharma",
            "new_email": "arjun@example.test",
            "admission_no": "ADM-500",
            "roll_number": "R-500",
            "date_of_birth": "2011-04-02",
            "gender": "Male",
            "address": "9 Test Road",
            "admission_date": "2026-06-01",
        }
        data.update(extra)
        return data

    def test_creating_a_student_creates_their_account(self):
        response = self.client.post(reverse("student-list"), self.payload())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        student = Student.objects.get(admission_no="ADM-500")
        self.assertEqual(student.user.username, "arjun.s")
        self.assertEqual(student.user.role, User.Role.STUDENT)
        self.assertEqual(student.user.get_full_name(), "Arjun Sharma")

    def test_the_new_account_lands_in_the_admins_organization(self):
        """Otherwise the student would be invisible to the admin who added them."""
        self.client.post(reverse("student-list"), self.payload())

        student = Student.objects.get(admission_no="ADM-500")
        self.assertEqual(student.organization, self.org)
        self.assertEqual(student.user.organization, self.org)

    def test_a_working_temporary_password_is_returned_once(self):
        response = self.client.post(reverse("student-list"), self.payload())
        password = response.data["temporary_password"]
        self.assertTrue(password)

        self.client.force_authenticate(None)
        login = self.client.post(
            reverse("login"), {"username": "arjun.s", "password": password}
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

        # Never returned again.
        self.client.force_authenticate(self.admin)
        listed = rows(self.client.get(reverse("student-list")))
        self.assertNotIn("temporary_password", listed[0])

    def test_a_duplicate_username_is_rejected_with_a_usable_message(self):
        self.client.post(reverse("student-list"), self.payload())
        response = self.client.post(
            reverse("student-list"),
            self.payload(admission_no="ADM-501", roll_number="R-501"),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_username", response.data)

    def test_a_username_is_required(self):
        payload = self.payload()
        del payload["new_username"]

        response = self.client.post(reverse("student-list"), payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_username", response.data)

    def test_a_rejected_student_leaves_no_orphan_account(self):
        """The account and the student are created as one unit."""
        before = User.objects.count()

        payload = self.payload()
        del payload["admission_no"]          # required, so the request fails
        response = self.client.post(reverse("student-list"), payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), before)

    def test_editing_a_student_updates_their_account_name(self):
        student = make_student(self.org, "s1", "ADM-1", "R-1")

        response = self.client.patch(
            reverse("student-detail", args=[student.id]),
            {"first_name": "Renamed", "last_name": "Person"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student.user.refresh_from_db()
        self.assertEqual(student.user.get_full_name(), "Renamed Person")

    def test_a_student_cannot_create_another_student(self):
        student = make_student(self.org, "s1", "ADM-1", "R-1")
        self.client.force_authenticate(student.user)

        response = self.client.post(reverse("student-list"), self.payload())
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
