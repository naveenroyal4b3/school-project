"""Activity log.

The project document's System Administration module asks for activity logs.
Beyond that, a system holding minors' records needs to answer "who changed
this, and when" - a disputed attendance mark or an altered exam result is not
resolvable without it.

Writes are recorded, reads are not: logging every list request would bury the
handful of entries that matter under thousands that do not.
"""

from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Created"
        UPDATE = "UPDATE", "Updated"
        DELETE = "DELETE", "Deleted"
        LOGIN = "LOGIN", "Signed in"
        LOGOUT = "LOGOUT", "Signed out"
        LOGIN_FAILED = "LOGIN_FAILED", "Failed sign-in"

    # Null rather than cascade: deleting a user must not erase the record of
    # what they did, which is the whole point of an audit trail.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="activity",
        null=True,
        blank=True,
    )

    # Denormalised so the entry stays readable after the account is gone.
    actor_username = models.CharField(max_length=150, blank=True)

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="activity",
        null=True,
        blank=True,
    )

    action = models.CharField(max_length=15, choices=Action.choices)

    # What was touched, as label and id rather than a generic relation: the
    # target may be deleted later, and the log must still say what it was.
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    target_label = models.CharField(max_length=200, blank=True)

    changes = models.JSONField(default=dict, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
        ]

    def __str__(self):
        who = self.actor_username or "system"
        return f"{who} {self.action} {self.target_type} {self.target_label}".strip()


def client_ip(request):
    """The caller's address, trusting the proxy header only for its first hop.

    Nginx sits in front in the documented deployment, so REMOTE_ADDR is the
    proxy. X-Forwarded-For is client-controlled beyond the first entry, so only
    that first entry is used.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record(request, action, instance=None, changes=None):
    """Write one entry. Never raises.

    An audit failure must not turn a successful save into an error the user
    sees; a missing log line is better than a lost fee payment.
    """
    try:
        user = getattr(request, "user", None)
        authenticated = bool(user and user.is_authenticated)

        ActivityLog.objects.create(
            actor=user if authenticated else None,
            actor_username=(user.username if authenticated else "") or "",
            organization=getattr(user, "organization", None) if authenticated else None,
            action=action,
            target_type=instance.__class__.__name__ if instance is not None else "",
            target_id=str(getattr(instance, "pk", "") or ""),
            target_label=str(instance)[:200] if instance is not None else "",
            changes=changes or {},
            ip_address=client_ip(request),
        )
    except Exception:  # noqa: BLE001 - logging must never break the request
        pass


class AuditedMixin:
    """Record create, update and delete on a DRF view.

    Mixed into the generic views rather than hooked to model signals, because
    a signal has no request and therefore cannot say who acted or from where.
    """

    def perform_create(self, serializer):
        super().perform_create(serializer)
        record(self.request, ActivityLog.Action.CREATE, serializer.instance)

    def perform_update(self, serializer):
        # Captured before the save, so the entry can show what actually moved.
        before = {
            field: str(getattr(serializer.instance, field, ""))
            for field in serializer.validated_data
            if hasattr(serializer.instance, field)
        }
        super().perform_update(serializer)

        after = {
            field: str(getattr(serializer.instance, field, ""))
            for field in serializer.validated_data
            if hasattr(serializer.instance, field)
        }
        changed = {
            field: {"from": before[field], "to": after[field]}
            for field in before
            if before[field] != after.get(field)
        }
        record(self.request, ActivityLog.Action.UPDATE, serializer.instance, changed)

    def perform_destroy(self, instance):
        # Recorded before deletion, while the label can still be read.
        record(self.request, ActivityLog.Action.DELETE, instance)
        super().perform_destroy(instance)
