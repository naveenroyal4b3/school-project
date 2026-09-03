"""Timetable clash prevention.

A double-booked teacher discovered on the first morning of term is not a
recoverable mistake, so the clashes are enforced in the database and reported
in language a timetabler can act on.
"""

import datetime

from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.academics.models import AcademicYear, ClassRoom, Subject
from apps.common.testing import make_admin, make_organization, make_teacher_user
from apps.teachers.models import Teacher

from .models import Period, Room, TimetableEntry


class TimetableFixture(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.year = AcademicYear.objects.create(
            organization=self.org, name="2026-27",
            start_date=datetime.date(2026, 6, 1), end_date=datetime.date(2027, 4, 30),
        )
        self.class_a = ClassRoom.objects.create(academic_year=self.year, name="Grade 10")
        self.class_b = ClassRoom.objects.create(academic_year=self.year, name="Grade 9")
        self.maths = Subject.objects.create(classroom=self.class_a, name="Maths", code="MTH")
        self.science = Subject.objects.create(classroom=self.class_a, name="Science", code="SCI")

        self.teacher = Teacher.objects.create(
            user=make_teacher_user(self.org), organization=self.org,
            employee_id="EMP-1", qualification="M.Sc", experience=5,
        )
        self.room = Room.objects.create(academic_year=self.year, name="Room 1")
        self.period = Period.objects.create(
            academic_year=self.year, name="Period 1", sequence=1,
            start_time=datetime.time(9, 0), end_time=datetime.time(9, 45),
        )

        self.client.force_authenticate(make_admin(self.org))

    def entry(self, **extra):
        data = {
            "classroom": self.class_a.id,
            "subject": self.maths.id,
            "teacher": self.teacher.id,
            "room": self.room.id,
            "period": self.period.id,
            "weekday": TimetableEntry.Weekday.MONDAY,
        }
        data.update(extra)
        # Multipart cannot encode None; omitting the key is how "no teacher"
        # or "no room" is expressed over the wire.
        return {key: value for key, value in data.items() if value is not None}


class ClashTests(TimetableFixture):
    def test_a_lesson_can_be_scheduled(self):
        response = self.client.post(reverse("timetable-list"), self.entry())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_a_teacher_cannot_be_in_two_classes_at_once(self):
        self.client.post(reverse("timetable-list"), self.entry())

        response = self.client.post(
            reverse("timetable-list"),
            self.entry(classroom=self.class_b.id, room=None),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("teacher", response.data)
        # The message names the conflicting lesson, not just "constraint failed".
        self.assertIn("Maths", str(response.data["teacher"]))

    def test_a_room_cannot_host_two_classes_at_once(self):
        self.client.post(reverse("timetable-list"), self.entry())

        response = self.client.post(
            reverse("timetable-list"),
            self.entry(classroom=self.class_b.id, teacher=None),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("room", response.data)

    def test_a_class_cannot_have_two_subjects_at_once(self):
        self.client.post(reverse("timetable-list"), self.entry())

        response = self.client.post(
            reverse("timetable-list"),
            self.entry(subject=self.science.id, teacher=None, room=None),
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT),
        )

    def test_the_same_slot_on_another_day_is_fine(self):
        self.client.post(reverse("timetable-list"), self.entry())

        response = self.client.post(
            reverse("timetable-list"),
            self.entry(weekday=TimetableEntry.Weekday.TUESDAY),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_editing_an_entry_does_not_clash_with_itself(self):
        created = self.client.post(reverse("timetable-list"), self.entry())

        response = self.client.patch(
            reverse("timetable-detail", args=[created.data["id"]]),
            {"subject": self.science.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_the_database_refuses_a_clash_even_without_the_serializer(self):
        """The serializer gives a good message; the constraint is the guarantee.
        Forms are not the only writer - imports and shell scripts exist too."""
        TimetableEntry.objects.create(
            classroom=self.class_a, subject=self.maths, teacher=self.teacher,
            period=self.period, weekday=TimetableEntry.Weekday.MONDAY,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TimetableEntry.objects.create(
                    classroom=self.class_b, subject=self.science, teacher=self.teacher,
                    period=self.period, weekday=TimetableEntry.Weekday.MONDAY,
                )


class ScheduleTests(TimetableFixture):
    def test_a_teachers_week_can_be_read(self):
        self.client.post(reverse("timetable-list"), self.entry())
        self.client.post(
            reverse("timetable-list"),
            self.entry(weekday=TimetableEntry.Weekday.TUESDAY),
        )

        response = self.client.get(
            reverse("teacher-schedule", args=[self.teacher.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_a_timetable_is_not_visible_to_another_college(self):
        self.client.post(reverse("timetable-list"), self.entry())

        other = make_organization("ORGB", "School B")
        self.client.force_authenticate(make_admin(other, "admin_b"))

        response = self.client.get(reverse("timetable-list"))
        self.assertEqual(response.data["count"], 0)


class PeriodTests(TimetableFixture):
    def test_a_period_ending_before_it_starts_is_rejected(self):
        response = self.client.post(reverse("period-list"), {
            "academic_year": self.year.id, "name": "Bad", "sequence": 9,
            "start_time": "11:00", "end_time": "10:00",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
