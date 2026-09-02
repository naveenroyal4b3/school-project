from django.db import models
from django.conf import settings

from apps.organizations.models import Organization
from apps.academics.models import AcademicYear, ClassRoom, Section
from apps.parents.models import Parent


class Student(models.Model):

    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="students",
        null=True,
        blank=True,
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="students",
        null=True,
        blank=True,
    )

    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name="students",
        null=True,
        blank=True,
    )

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="students",
        null=True,
        blank=True,
    )

    parent = models.ForeignKey(
        Parent,
        on_delete=models.SET_NULL,
        related_name="students",
        null=True,
        blank=True,
    )

    admission_no = models.CharField(
        max_length=20,
        unique=True,
    )

    roll_number = models.CharField(
        max_length=20,
        unique=True,
    )

    date_of_birth = models.DateField()

    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
    )

    address = models.TextField()

    admission_date = models.DateField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.admission_no} - {self.user.first_name} {self.user.last_name}"