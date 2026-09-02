"""Transport & Bus Management.

Covers the document's Drivers, Buses & Bus Tracking, Routes and GPS Location
tables, and the relationships One Driver -> One Bus, One Bus -> One Route,
One Bus -> Many Students, One Route -> Many Bus Tracking Records.
"""

from django.conf import settings
from django.db import models

from apps.organizations.models import Organization
from apps.students.models import Student


class Driver(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="driver_profile",
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="drivers",
    )

    license_number = models.CharField(max_length=30, unique=True)

    license_expiry = models.DateField()

    experience_years = models.PositiveSmallIntegerField(default=0)

    address = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.license_number})"


class Route(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="routes",
    )

    name = models.CharField(max_length=100)

    code = models.CharField(max_length=20)

    start_point = models.CharField(max_length=150)

    end_point = models.CharField(max_length=150)

    distance_km = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    estimated_duration_minutes = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_route_code_per_organization",
            )
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class RouteStop(models.Model):
    """An ordered pickup/drop point on a route, with coordinates so the map
    view can draw the route alongside the live bus position."""

    route = models.ForeignKey(
        Route,
        on_delete=models.CASCADE,
        related_name="stops",
    )

    name = models.CharField(max_length=150)

    sequence = models.PositiveSmallIntegerField()

    latitude = models.DecimalField(max_digits=9, decimal_places=6)

    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    scheduled_arrival = models.TimeField(blank=True, null=True)

    class Meta:
        ordering = ["route", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["route", "sequence"],
                name="unique_stop_sequence_per_route",
            )
        ]

    def __str__(self):
        return f"{self.route.code} #{self.sequence} {self.name}"


class Bus(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="buses",
    )

    registration_number = models.CharField(max_length=20, unique=True)

    model = models.CharField(max_length=100, blank=True, null=True)

    capacity = models.PositiveSmallIntegerField(default=40)

    # One Driver -> One Bus, so this is a OneToOne rather than an FK.
    driver = models.OneToOneField(
        Driver,
        on_delete=models.SET_NULL,
        related_name="bus",
        null=True,
        blank=True,
    )

    # One Bus -> One Route.
    route = models.ForeignKey(
        Route,
        on_delete=models.SET_NULL,
        related_name="buses",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "buses"

    def __str__(self):
        return self.registration_number


class StudentTransport(models.Model):
    """Assigns a student to a bus (One Bus -> Many Students).

    Held here rather than as a field on Student so the transport module owns
    its own concerns, and so a pickup stop can travel with the assignment.
    """

    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name="transport",
    )

    bus = models.ForeignKey(
        Bus,
        on_delete=models.CASCADE,
        related_name="students",
    )

    pickup_stop = models.ForeignKey(
        RouteStop,
        on_delete=models.SET_NULL,
        related_name="students",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.admission_no} -> {self.bus.registration_number}"


class Trip(models.Model):
    """One run of a bus along its route. Drivers start and end trips; live
    locations attach to the trip that was open when they were recorded."""

    class TripType(models.TextChoices):
        MORNING = "MORNING", "Morning"
        EVENING = "EVENING", "Evening"

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name="trips")

    driver = models.ForeignKey(
        Driver,
        on_delete=models.SET_NULL,
        related_name="trips",
        null=True,
        blank=True,
    )

    route = models.ForeignKey(
        Route,
        on_delete=models.SET_NULL,
        related_name="trips",
        null=True,
        blank=True,
    )

    trip_type = models.CharField(
        max_length=10,
        choices=TripType.choices,
        default=TripType.MORNING,
    )

    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )

    started_at = models.DateTimeField(blank=True, null=True)

    ended_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.bus.registration_number} {self.trip_type} ({self.status})"


class BusLocation(models.Model):
    """A GPS ping from a driver's device (the document's GPS Location table).

    Rows are append-only and high volume, so the bus/timestamp index matters:
    the tracking endpoint always asks for the newest row for one bus.
    """

    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name="locations")

    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="locations",
        null=True,
        blank=True,
    )

    latitude = models.DecimalField(max_digits=9, decimal_places=6)

    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    speed_kmph = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["bus", "-recorded_at"])]

    def __str__(self):
        return f"{self.bus.registration_number} @ {self.latitude},{self.longitude}"
