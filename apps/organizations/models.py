from django.db import models


class Organization(models.Model):

    ORGANIZATION_TYPES = [
        ("School", "School"),
        ("College", "College"),
        ("Coaching Center", "Coaching Center"),
        ("University", "University"),
        ("Training Institute", "Training Institute"),
    ]

    SUBSCRIPTION_PLANS = [
        ("Free", "Free"),
        ("Basic", "Basic"),
        ("Premium", "Premium"),
        ("Enterprise", "Enterprise"),
    ]

    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
    ]

    organization_code = models.CharField(
        max_length=20,
        unique=True
    )

    organization_name = models.CharField(
        max_length=200
    )

    organization_type = models.CharField(
        max_length=30,
        choices=ORGANIZATION_TYPES
    )

    logo = models.ImageField(
        upload_to="organization_logos/",
        blank=True,
        null=True
    )

    primary_color = models.CharField(
        max_length=20,
        default="#1976D2"
    )

    secondary_color = models.CharField(
        max_length=20,
        default="#FFFFFF"
    )

    address = models.TextField()

    city = models.CharField(
        max_length=100
    )

    state = models.CharField(
        max_length=100
    )

    country = models.CharField(
        max_length=100
    )

    pincode = models.CharField(
        max_length=10
    )

    phone = models.CharField(
        max_length=15
    )

    email = models.EmailField()

    website = models.URLField(
        blank=True
    )

    subscription_plan = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_PLANS,
        default="Free"
    )

    subscription_start = models.DateField()

    subscription_end = models.DateField()

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="Active"
    )

    # Attendance timing. An ID-card scan before day_start_time still counts as
    # PRESENT; one after late_after_time is marked LATE. Held per organization
    # because schools and colleges on the same platform start at different hours.
    day_start_time = models.TimeField(default="08:00")

    late_after_time = models.TimeField(default="09:15")

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        # Stable ordering: pagination over an unordered queryset can
        # repeat or skip rows between pages.
        ordering = ["organization_name"]

    def __str__(self):
        return f"{self.organization_name} ({self.organization_code})"