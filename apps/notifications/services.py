"""Delivery for notifications.

The document names an "SMS Gateway API" without choosing one, so delivery sits
behind a small backend interface. The default backend logs instead of sending,
which keeps development and the test suite from making network calls or
charging for messages; a real gateway is a drop-in replacement configured
through ``SMS_BACKEND`` in settings.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.module_loading import import_string

from .models import Notification

logger = logging.getLogger(__name__)


class ConsoleSMSBackend:
    """Records the message in the log. Used in development and tests."""

    def send(self, phone_number, message):
        logger.info("SMS -> %s: %s", phone_number, message)
        return True


def get_sms_backend():
    path = getattr(settings, "SMS_BACKEND", None)
    if not path:
        return ConsoleSMSBackend()
    return import_string(path)()


def notify(recipient, title, message, *, notification_type, channel, student=None, organization=None):
    """Create a notification and attempt delivery.

    Always returns the stored Notification. A delivery failure is recorded on
    the row rather than raised, because the callers are things like a bus scan
    or a fee payment: those must not fail because an SMS gateway was down.
    """

    notification = Notification.objects.create(
        organization=organization,
        recipient=recipient,
        student=student,
        title=title,
        message=message,
        notification_type=notification_type,
        channel=channel,
    )

    try:
        if channel == Notification.Channel.SMS:
            phone = getattr(recipient, "phone_number", None)
            if not phone:
                raise ValueError("recipient has no phone number")
            get_sms_backend().send(phone, message)

        elif channel == Notification.Channel.EMAIL:
            if not recipient.email:
                raise ValueError("recipient has no email address")
            send_mail(
                subject=title,
                message=message,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
                recipient_list=[recipient.email],
                fail_silently=False,
            )

        # IN_APP needs no transport; storing the row is the delivery.
        notification.status = Notification.Status.SENT
        notification.sent_at = timezone.now()

    except Exception as exc:  # noqa: BLE001 - failure must not break the caller
        logger.warning("notification %s delivery failed: %s", notification.pk, exc)
        notification.status = Notification.Status.FAILED
        notification.error_message = str(exc)[:300]

    notification.save(update_fields=["status", "sent_at", "error_message"])
    return notification


def notify_guardians(student, title, message, *, notification_type, channel=None):
    """Send an alert to a student's guardian.

    Returns the notifications created - an empty list when the student has no
    parent on file, which is a data gap rather than an error.
    """

    parent = student.parent
    if parent is None:
        return []

    return [
        notify(
            parent.user,
            title,
            message,
            notification_type=notification_type,
            channel=channel or Notification.Channel.SMS,
            student=student,
            organization=student.organization,
        )
    ]
