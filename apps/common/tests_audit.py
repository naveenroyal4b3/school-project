"""Activity log.

A system holding minors' records has to answer "who changed this, and when".
A disputed attendance mark or an altered exam result is not resolvable without
it.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .audit import ActivityLog
from .testing import make_admin, make_organization, make_student, rows


class AuditTrailTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.admin = make_admin(self.org)
        self.client.force_authenticate(self.admin)

    def test_creating_a_student_is_recorded(self):
        self.client.post(
            reverse("student-list"),
            {
                "new_username": "logged.one",
                "first_name": "Logged",
                "admission_no": "ADM-700",
                "roll_number": "R-700",
                "date_of_birth": "2011-01-01",
                "gender": "Male",
                "address": "1 Road",
                "admission_date": "2026-06-01",
            },
        )

        entry = ActivityLog.objects.get(action=ActivityLog.Action.CREATE)
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.actor_username, self.admin.username)
        self.assertEqual(entry.target_type, "Student")
        self.assertEqual(entry.organization, self.org)

    def test_an_update_records_what_actually_changed(self):
        student = make_student(self.org, "s1", "ADM-1", "R-1")

        self.client.patch(
            reverse("student-detail", args=[student.id]), {"roll_number": "R-999"}
        )

        entry = ActivityLog.objects.get(action=ActivityLog.Action.UPDATE)
        self.assertIn("roll_number", entry.changes)
        self.assertEqual(entry.changes["roll_number"]["from"], "R-1")
        self.assertEqual(entry.changes["roll_number"]["to"], "R-999")

    def test_a_deletion_keeps_the_label_of_what_was_deleted(self):
        student = make_student(self.org, "s1", "ADM-1", "R-1")
        self.client.delete(reverse("student-detail", args=[student.id]))

        entry = ActivityLog.objects.get(action=ActivityLog.Action.DELETE)
        self.assertIn("ADM-1", entry.target_label)

    def test_the_trail_survives_the_actor_being_deleted(self):
        """Otherwise deleting a user erases the record of what they did, which
        is the one thing an audit log must not allow."""
        leaver = make_admin(self.org, "departing.admin")
        self.client.force_authenticate(leaver)

        student = make_student(self.org, "s1", "ADM-1", "R-1")
        response = self.client.patch(
            reverse("student-detail", args=[student.id]), {"roll_number": "R-2"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        leaver_name = leaver.username
        leaver.delete()

        entry = ActivityLog.objects.get(action=ActivityLog.Action.UPDATE)
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.actor_username, leaver_name)


class AuthEventTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        make_admin(self.org, "admin1")

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_sign_in_and_sign_out_are_recorded(self):
        self.client.post(
            reverse("login"), {"username": "admin1", "password": "TestPass!2026"}
        )
        self.client.post(reverse("logout"), {})

        actions = set(ActivityLog.objects.values_list("action", flat=True))
        self.assertIn(ActivityLog.Action.LOGIN, actions)
        self.assertIn(ActivityLog.Action.LOGOUT, actions)

    def test_failed_sign_ins_are_recorded(self):
        """A brute-force should show in a durable trail, not only in a throttle
        counter that lives in the cache."""
        self.client.post(
            reverse("login"), {"username": "admin1", "password": "wrong"}
        )

        self.assertTrue(
            ActivityLog.objects.filter(action=ActivityLog.Action.LOGIN_FAILED).exists()
        )


class AuditVisibilityTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.other = make_organization("ORGB", "School B")
        self.admin = make_admin(self.org)

        ActivityLog.objects.create(
            action=ActivityLog.Action.CREATE, organization=self.org,
            actor_username="ours", target_type="Student",
        )
        ActivityLog.objects.create(
            action=ActivityLog.Action.CREATE, organization=self.other,
            actor_username="theirs", target_type="Student",
        )

    def test_admins_see_only_their_own_colleges_trail(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("activity-log"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [row["actor_username"] for row in rows(response)]
        self.assertEqual(names, ["ours"])

    def test_faculty_and_students_cannot_read_the_trail(self):
        for username, role in [("t1", User.Role.TEACHER), ("s1", User.Role.STUDENT)]:
            with self.subTest(role=role):
                from apps.common.testing import make_user
                self.client.force_authenticate(make_user(username, role, self.org))
                self.assertEqual(
                    self.client.get(reverse("activity-log")).status_code,
                    status.HTTP_403_FORBIDDEN,
                )

    def test_the_trail_is_read_only(self):
        """An audit log that can be amended proves nothing."""
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse("activity-log"), {})

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
