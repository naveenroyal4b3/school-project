from django.db import models
from django.conf import settings
from apps.organizations.models import Organization


class Teacher(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="teachers",
    )

    employee_id = models.CharField(
        max_length=20,
        unique=True,
    )

    qualification = models.CharField(
        max_length=100,
        blank=True,
    )

    experience = models.PositiveIntegerField(
        default=0,
        help_text="Experience in years",
    )

    profile_image = models.ImageField(
        upload_to="teachers/",
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Stable ordering: pagination over an unordered queryset can
        # repeat or skip rows between pages.
        ordering = ["employee_id"]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"