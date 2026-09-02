from django.conf import settings
from django.db import models

from apps.organizations.models import Organization


class Parent(models.Model):
    """A guardian who monitors one or more students.

    The document's relationship table specifies One Parent -> Many Students,
    so the link lives on ``Student.parent`` rather than here.
    """

    RELATIONSHIP_CHOICES = [
        ("Father", "Father"),
        ("Mother", "Mother"),
        ("Guardian", "Guardian"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_profile",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="parents",
        null=True,
        blank=True,
    )

    relationship = models.CharField(
        max_length=10,
        choices=RELATIONSHIP_CHOICES,
        default="Guardian",
    )

    occupation = models.CharField(max_length=100, blank=True, null=True)

    # Kept separate from User.phone_number: notifications go to whichever
    # number the guardian nominated for alerts, which is not always the number
    # they sign in with.
    alternate_phone = models.CharField(max_length=15, blank=True, null=True)

    address = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Stable ordering: pagination over an unordered queryset can
        # repeat or skip rows between pages.
        ordering = ["user__first_name", "id"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.relationship})"
