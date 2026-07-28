from django.db import models
from django.contrib.auth.models import AbstractUser
from apps.organizations.models import Organization


class User(AbstractUser):

    email = models.EmailField(unique=True)

    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
        ORGANIZATION_ADMIN = "ORGANIZATION_ADMIN", "Organization Admin"
        TEACHER = "TEACHER", "Teacher"
        PARENT = "PARENT", "Parent"
        STUDENT = "STUDENT", "Student"
        DRIVER = "DRIVER", "Driver"

    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
    )

    phone_number = models.CharField(
        max_length=15,
        unique=True,
        null=True,
        blank=True,
    )

    profile_image = models.ImageField(
        upload_to="profiles/",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} ({self.role})"