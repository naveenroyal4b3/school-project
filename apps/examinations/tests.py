import datetime
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.academics.models import AcademicYear, ClassRoom, Subject
from apps.common.testing import (
    make_admin,
    make_organization,
    make_parent,
    make_student,
    make_teacher_user,
)
from apps.notifications.models import Notification

from .models import Exam, ExamSchedule, Result


class ExamFixtureMixin:
    def build_fixture(self):
        self.org = make_organization("ORGA", "School A")
        self.year = AcademicYear.objects.create(
            organization=self.org,
            name="2026-27",
            start_date=datetime.date(2026, 6, 1),
            end_date=datetime.date(2027, 4, 30),
        )
        self.classroom = ClassRoom.objects.create(academic_year=self.year, name="Grade 10")
        self.subject = Subject.objects.create(classroom=self.classroom, name="Maths", code="MTH")

        self.exam = Exam.objects.create(
            organization=self.org,
            academic_year=self.year,
            name="Midterm",
            exam_type=Exam.ExamType.MIDTERM,
            start_date=datetime.date(2026, 10, 1),
            end_date=datetime.date(2026, 10, 10),
        )
        self.schedule = ExamSchedule.objects.create(
            exam=self.exam,
            subject=self.subject,
            classroom=self.classroom,
            exam_date=datetime.date(2026, 10, 1),
            start_time=datetime.time(9, 0),
            end_time=datetime.time(12, 0),
            max_marks=Decimal("100.00"),
            passing_marks=Decimal("35.00"),
        )


class GradeCalculationTests(ExamFixtureMixin, APITestCase):
    def setUp(self):
        self.build_fixture()
        self.student = make_student(self.org, classroom=self.classroom)

    def test_grades_follow_the_percentage_bands(self):
        for marks, expected in [
            ("95.00", "A+"), ("85.00", "A"), ("75.00", "B+"),
            ("65.00", "B"), ("55.00", "C"), ("45.00", "D"), ("20.00", "F"),
        ]:
            with self.subTest(marks=marks):
                result = Result.objects.create(
                    student=self.student,
                    exam_schedule=self.schedule,
                    marks_obtained=Decimal(marks),
                )
                self.assertEqual(result.grade, expected)
                result.delete()

    def test_pass_flag_uses_the_papers_passing_mark(self):
        passing = Result.objects.create(
            student=self.student, exam_schedule=self.schedule, marks_obtained=Decimal("35.00")
        )
        self.assertTrue(passing.is_pass)
        passing.delete()

        failing = Result.objects.create(
            student=self.student, exam_schedule=self.schedule, marks_obtained=Decimal("34.99")
        )
        self.assertFalse(failing.is_pass)

    def test_grade_is_recomputed_when_marks_are_corrected(self):
        result = Result.objects.create(
            student=self.student, exam_schedule=self.schedule, marks_obtained=Decimal("20.00")
        )
        self.assertEqual(result.grade, "F")

        result.marks_obtained = Decimal("91.00")
        result.save()
        result.refresh_from_db()

        self.assertEqual(result.grade, "A+")
        self.assertTrue(result.is_pass)

    def test_client_cannot_dictate_the_grade(self):
        self.client.force_authenticate(make_teacher_user(self.org))

        response = self.client.post(
            reverse("result-list"),
            {
                "student": self.student.id,
                "exam_schedule": self.schedule.id,
                "marks_obtained": "10.00",
                "grade": "A+",
                "is_pass": True,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Result.objects.get().grade, "F")
        self.assertFalse(Result.objects.get().is_pass)

    def test_marks_above_the_maximum_are_rejected(self):
        self.client.force_authenticate(make_teacher_user(self.org, "t2"))

        response = self.client.post(
            reverse("result-list"),
            {
                "student": self.student.id,
                "exam_schedule": self.schedule.id,
                "marks_obtained": "150.00",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ResultVisibilityTests(ExamFixtureMixin, APITestCase):
    def setUp(self):
        self.build_fixture()
        self.parent = make_parent(self.org)
        self.student = make_student(self.org, parent=self.parent, classroom=self.classroom)
        Result.objects.create(
            student=self.student, exam_schedule=self.schedule, marks_obtained=Decimal("80.00")
        )

    def test_unpublished_results_are_hidden_from_students(self):
        self.client.force_authenticate(self.student.user)
        response = self.client.get(reverse("result-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data), [])

    def test_faculty_see_unpublished_results(self):
        self.client.force_authenticate(make_teacher_user(self.org))
        response = self.client.get(reverse("result-list"))

        self.assertEqual(len(response.data), 1)

    def test_publishing_reveals_results_and_alerts_guardians(self):
        self.client.force_authenticate(make_admin(self.org))
        response = self.client.post(reverse("exam-publish", args=[self.exam.id]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.exam.refresh_from_db()
        self.assertTrue(self.exam.is_published)

        notification = Notification.objects.get()
        self.assertEqual(notification.recipient, self.parent.user)
        self.assertEqual(notification.notification_type, Notification.Type.EXAM)

        self.client.force_authenticate(self.student.user)
        self.assertEqual(len(self.client.get(reverse("result-list")).data), 1)

    def test_publishing_twice_does_not_send_duplicate_alerts(self):
        self.client.force_authenticate(make_admin(self.org))
        self.client.post(reverse("exam-publish", args=[self.exam.id]))
        self.client.post(reverse("exam-publish", args=[self.exam.id]))

        self.assertEqual(Notification.objects.count(), 1)


class ExamScheduleValidationTests(ExamFixtureMixin, APITestCase):
    def setUp(self):
        self.build_fixture()
        self.client.force_authenticate(make_admin(self.org))

    def test_end_time_must_follow_start_time(self):
        response = self.client.post(
            reverse("examschedule-list"),
            {
                "exam": self.exam.id,
                "subject": self.subject.id,
                "exam_date": "2026-10-02",
                "start_time": "12:00",
                "end_time": "09:00",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_passing_marks_cannot_exceed_max_marks(self):
        response = self.client.post(
            reverse("examschedule-list"),
            {
                "exam": self.exam.id,
                "subject": self.subject.id,
                "exam_date": "2026-10-02",
                "start_time": "09:00",
                "end_time": "12:00",
                "max_marks": "50.00",
                "passing_marks": "80.00",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
