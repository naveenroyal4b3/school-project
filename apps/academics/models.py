from django.db import models
from apps.organizations.models import Organization


class AcademicYear(models.Model):

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="academic_years",
    )

    name = models.CharField(max_length=50)

    start_date = models.DateField()

    end_date = models.DateField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class ClassRoom(models.Model):

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="classrooms",
    )

    name = models.CharField(max_length=50)

    description = models.TextField(
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Section(models.Model):

    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name="sections",
    )

    name = models.CharField(max_length=10)

    capacity = models.PositiveIntegerField(default=40)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.classroom.name} - {self.name}"


class Subject(models.Model):

    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name="subjects",
    )

    name = models.CharField(max_length=100)

    code = models.CharField(
        max_length=20,
        unique=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"