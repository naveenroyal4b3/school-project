from django.db import models
from apps.organizations.models import Organization


class Department(models.Model):
    """A teaching department, e.g. Computer Science. One department has many
    courses (project document, Relationships)."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="departments",
    )

    name = models.CharField(max_length=100)

    code = models.CharField(max_length=20)

    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Codes are unique per college, not globally - two organizations may
        # both run a department coded "CSE".
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_department_code_per_organization",
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Course(models.Model):
    """A programme of study offered by a department, e.g. B.Tech CSE."""

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="courses",
    )

    name = models.CharField(max_length=100)

    code = models.CharField(max_length=20)

    duration_years = models.PositiveSmallIntegerField(default=4)

    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "code"],
                name="unique_course_code_per_department",
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


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