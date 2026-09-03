"""Archiving instead of deleting.

Deleting a student cascaded away their attendance, fee payments and exam
results. A school that removes a leaver would lose the record that they ever
paid — which is exactly what it needs years later when someone asks for a
transcript or disputes a fee.

Records are therefore archived: hidden from every list, kept in the database,
and restorable. Hard deletion stays available to a platform superuser for
genuine erasure requests, which is a deliberate act rather than the default.
"""

from django.db import models
from django.utils import timezone


class ArchivableQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(archived_at__isnull=True)

    def archived(self):
        return self.filter(archived_at__isnull=False)

    def archive(self):
        return self.update(archived_at=timezone.now())


class ArchivableManager(models.Manager.from_queryset(ArchivableQuerySet)):
    """Default manager, returning only live rows.

    ``all_objects`` on the model reaches archived rows. The default is the safe
    one, so a view that forgets to filter shows current records rather than
    quietly resurrecting leavers into this year's class list.
    """

    def get_queryset(self):
        return super().get_queryset().filter(archived_at__isnull=True)


class ArchivableModel(models.Model):
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = ArchivableManager()
    all_objects = models.Manager.from_queryset(ArchivableQuerySet)()

    class Meta:
        abstract = True

    @property
    def is_archived(self):
        return self.archived_at is not None

    def archive(self):
        if self.archived_at is None:
            self.archived_at = timezone.now()
            self.save(update_fields=["archived_at"])

    def restore(self):
        if self.archived_at is not None:
            self.archived_at = None
            self.save(update_fields=["archived_at"])


class ArchiveOnDeleteMixin:
    """Make DELETE archive rather than destroy.

    A platform superuser can still erase permanently with ?hard=true, for a
    genuine erasure request. Nobody else can, because a mistaken click must not
    be able to destroy a payment history.
    """

    def perform_destroy(self, instance):
        hard = self.request.query_params.get("hard") == "true"
        user = self.request.user

        if hard and (user.is_superuser or user.role == "SUPER_ADMIN"):
            instance.delete()
            return

        instance.archive()
