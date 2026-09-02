"""Access-control tests.

These cover the two failure modes that matter most for a system holding
minors' personal data: an endpoint that answers without authentication, and
one tenant reading another tenant's records.
"""

import datetime

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.testing import rows

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.students.models import Student


def make_organization(code, name):
    return Organization.objects.create(
        organization_code=code,
        organization_name=name,
        organization_type="School",
        address="1 Test Road",
        city="Testville",
        state="TS",
        country="Testland",
        pincode="123456",
        phone="0000000000",
        email=f"{code.lower()}@example.test",
        subscription_start=datetime.date(2026, 1, 1),
        subscription_end=datetime.date(2027, 1, 1),
    )


def make_user(username, role, organization=None):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="TestPass!2026",
        role=role,
        organization=organization,
    )


def make_student(user, organization, admission_no, roll_number):
    return Student.objects.create(
        user=user,
        organization=organization,
        admission_no=admission_no,
        roll_number=roll_number,
        date_of_birth=datetime.date(2010, 5, 1),
        gender="Male",
        address="2 Test Lane",
        admission_date=datetime.date(2026, 6, 1),
    )


class AuthenticationRequiredTests(APITestCase):
    """No endpoint holding student data may answer an anonymous caller."""

    def test_protected_endpoints_reject_anonymous_requests(self):
        for name in [
            "student-list",
            "teacher-list",
            "parent-list",
            "subject-list-create",
            "department-list-create",
        ]:
            with self.subTest(endpoint=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RolePermissionTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORG1", "Test School")
        self.admin = make_user("admin1", User.Role.ORGANIZATION_ADMIN, self.org)
        self.student_user = make_user("student1", User.Role.STUDENT, self.org)
        self.teacher_user = make_user("teacher1", User.Role.TEACHER, self.org)

    def test_student_may_read_but_not_create(self):
        self.client.force_authenticate(self.student_user)

        self.assertEqual(
            self.client.get(reverse("student-list")).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.post(reverse("student-list"), {}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_may_create(self):
        self.client.force_authenticate(self.admin)
        subject_user = make_user("newstudent", User.Role.STUDENT, self.org)

        response = self.client.post(
            reverse("student-list"),
            {
                "user": subject_user.id,
                "organization": self.org.id,
                "admission_no": "ADM-100",
                "roll_number": "R-100",
                "date_of_birth": "2010-05-01",
                "gender": "Male",
                "address": "3 Test Lane",
                "admission_date": "2026-06-01",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_faculty_may_write_academic_records_but_student_may_not(self):
        self.client.force_authenticate(self.teacher_user)
        self.assertNotEqual(
            self.client.post(reverse("department-list-create"), {}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.client.force_authenticate(self.student_user)
        self.assertEqual(
            self.client.post(reverse("department-list-create"), {}).status_code,
            status.HTTP_403_FORBIDDEN,
        )


class OrganizationScopingTests(APITestCase):
    """One college must never see another college's students."""

    def setUp(self):
        self.org_a = make_organization("ORGA", "School A")
        self.org_b = make_organization("ORGB", "School B")

        make_student(
            make_user("a_student", User.Role.STUDENT, self.org_a),
            self.org_a, "ADM-A", "R-A",
        )
        self.b_student = make_student(
            make_user("b_student", User.Role.STUDENT, self.org_b),
            self.org_b, "ADM-B", "R-B",
        )

        self.admin_a = make_user("admin_a", User.Role.ORGANIZATION_ADMIN, self.org_a)

    def test_list_excludes_other_organizations(self):
        self.client.force_authenticate(self.admin_a)
        response = self.client.get(reverse("student-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned = [row["admission_no"] for row in rows(response)]
        self.assertEqual(returned, ["ADM-A"])

    def test_detail_of_other_organization_is_not_found(self):
        self.client.force_authenticate(self.admin_a)
        response = self.client.get(
            reverse("student-detail", args=[self.b_student.id])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_without_organization_sees_nothing(self):
        orphan = make_user("orphan", User.Role.ORGANIZATION_ADMIN, None)
        self.client.force_authenticate(orphan)

        response = self.client.get(reverse("student-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(rows(response)), [])


class RegistrationHardeningTests(APITestCase):
    def test_self_registration_cannot_choose_a_role(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "escalate",
                "email": "escalate@example.test",
                "password": "TestPass!2026",
                "role": User.Role.SUPER_ADMIN,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            User.objects.get(username="escalate").role,
            User.Role.STUDENT,
        )

    def test_registration_response_does_not_leak_credentials(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "leaky",
                "email": "leaky@example.test",
                "password": "TestPass!2026",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        for leaked in ["password", "is_superuser", "is_staff", "user_permissions"]:
            self.assertNotIn(leaked, response.data["user"])

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            reverse("register"),
            {"username": "weak", "email": "weak@example.test", "password": "123"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PaginationTests(APITestCase):
    """Screens that print ID cards or take a roll call ask for the whole set.
    A silently ignored page_size would show them only the first 25."""

    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        for i in range(30):
            make_student(
                make_user(f"s{i}", User.Role.STUDENT, self.org),
                self.org, f"ADM-{i:03d}", f"R-{i:03d}",
            )
        self.client.force_authenticate(make_user("admin1", User.Role.ORGANIZATION_ADMIN, self.org))

    def test_default_page_size_is_applied(self):
        response = self.client.get(reverse("student-list"))
        self.assertEqual(len(rows(response)), 25)
        self.assertEqual(response.data["count"], 30)

    def test_page_size_can_be_raised(self):
        response = self.client.get(reverse("student-list"), {"page_size": 100})
        self.assertEqual(len(rows(response)), 30)

    def test_page_size_is_capped(self):
        """The parameter must not become a way to pull an entire college."""
        response = self.client.get(reverse("student-list"), {"page_size": 99999})
        self.assertEqual(len(rows(response)), 30)  # capped at 1000, all 30 fit
