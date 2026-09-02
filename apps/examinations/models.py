"""Examination & Result Management.

Covers the document's Examinations & Results tables and its Grade Calculation
and Performance Reports features. One Student -> Many Examination Results.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.academics.models import AcademicYear, ClassRoom, Subject
from apps.organizations.models import Organization
from apps.students.models import Student


class Exam(models.Model):
    class ExamType(models.TextChoices):
        UNIT_TEST = "UNIT_TEST", "Unit Test"
        MIDTERM = "MIDTERM", "Midterm"
        FINAL = "FINAL", "Final"
        PRACTICAL = "PRACTICAL", "Practical"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="exams",
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="exams",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=100)

    exam_type = models.CharField(
        max_length=15,
        choices=ExamType.choices,
        default=ExamType.UNIT_TEST,
    )

    start_date = models.DateField()

    end_date = models.DateField()

    # Results stay hidden from students and parents until an admin publishes
    # them, so a half-entered mark sheet is never visible.
    is_published = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.name} ({self.exam_type})"


class ExamSchedule(models.Model):
    """One paper: a subject sat by a class on a date."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="schedules")

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="exam_schedules",
    )

    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name="exam_schedules",
        null=True,
        blank=True,
    )

    exam_date = models.DateField()

    start_time = models.TimeField()

    end_time = models.TimeField()

    max_marks = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("100.00")
    )

    passing_marks = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("35.00")
    )

    class Meta:
        ordering = ["exam_date", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "subject", "classroom"],
                name="unique_paper_per_exam_subject_classroom",
            )
        ]

    def __str__(self):
        return f"{self.exam.name} - {self.subject.name} on {self.exam_date}"


class Result(models.Model):
    """A student's marks for one paper.

    ``grade`` and ``is_pass`` are computed on save rather than accepted from the
    client: a grade that disagrees with the marks it came from is worse than no
    grade at all.
    """

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="results",
    )

    exam_schedule = models.ForeignKey(
        ExamSchedule,
        on_delete=models.CASCADE,
        related_name="results",
    )

    marks_obtained = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )

    grade = models.CharField(max_length=2, blank=True, editable=False)

    is_pass = models.BooleanField(default=False, editable=False)

    remarks = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "exam_schedule"],
                name="unique_result_per_student_paper",
            )
        ]

    @property
    def percentage(self):
        max_marks = self.exam_schedule.max_marks
        if not max_marks:
            return Decimal("0")
        return (self.marks_obtained / max_marks) * 100

    @staticmethod
    def grade_for(percentage):
        for threshold, letter in (
            (90, "A+"), (80, "A"), (70, "B+"),
            (60, "B"), (50, "C"), (40, "D"),
        ):
            if percentage >= threshold:
                return letter
        return "F"

    def save(self, *args, **kwargs):
        self.grade = self.grade_for(self.percentage)
        self.is_pass = self.marks_obtained >= self.exam_schedule.passing_marks
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.admission_no} {self.exam_schedule.subject.name} {self.grade}"
