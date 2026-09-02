"""Notification & Communication.

Covers the document's Notifications table and the SMS/Email logs shown in its
architecture diagram. A notification is stored first and delivered second, so a
failing SMS gateway loses the delivery attempt but never the record that an
alert was owed.
"""

from django.conf import settings
from django.db import models

from apps.organizations.models import Organization
from apps.students.models import Student


class Notification(models.Model):
    class Type(models.TextChoices):
        ATTENDANCE = "ATTENDANCE", "Attendance"
        TRANSPORT = "TRANSPORT", "Transport"
        FEE = "FEE", "Fee"
        EXAM = "EXAM", "Exam"
        GENERAL = "GENERAL", "General"

    class Channel(models.TextChoices):
        SMS = "SMS", "SMS"
        EMAIL = "EMAIL", "Email"
        IN_APP = "IN_APP", "In App"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    # One Student -> Many Notifications. Set when the alert concerns a
    # particular student, e.g. a parent being told their child boarded a bus.
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )

    title = models.CharField(max_length=150)

    message = models.TextField()

    notification_type = models.CharField(
        max_length=15,
        choices=Type.choices,
        default=Type.GENERAL,
    )

    channel = models.CharField(
        max_length=10,
        choices=Channel.choices,
        default=Channel.IN_APP,
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )

    error_message = models.CharField(max_length=300, blank=True, null=True)

    is_read = models.BooleanField(default=False)

    sent_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "-created_at"])]

    def __str__(self):
        return f"{self.notification_type} -> {self.recipient} ({self.status})"
