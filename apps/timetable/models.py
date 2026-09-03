"""Timetable & Class Management.

The block the project document's architecture diagram labels "Timetable & Class
Management — Class Timetable, Teacher Schedule, Room / Subject".

A period is one subject taught to one class by one teacher, in one room, at one
time on one weekday. The clashes that matter are enforced in the database
rather than only in a form, because a double-booked teacher discovered on the
morning of term is not a recoverable mistake.
"""

from django.db import models

from apps.academics.models import AcademicYear, ClassRoom, Section, Subject
from apps.teachers.models import Teacher


class Room(models.Model):
    """A physical room. Optional on a period: a school without room management
    still wants a timetable."""

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="rooms",
    )

    name = models.CharField(max_length=50)

    capacity = models.PositiveSmallIntegerField(default=40)

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "name"],
                name="unique_room_name_per_year",
            )
        ]

    def __str__(self):
        return self.name


class Period(models.Model):
    """A named slot in the school day, e.g. "Period 3", 11:00-11:45.

    Defined once per year rather than repeated on every timetable entry, so
    moving the lunch break moves it everywhere.
    """

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="periods",
    )

    name = models.CharField(max_length=30)

    sequence = models.PositiveSmallIntegerField()

    start_time = models.TimeField()

    end_time = models.TimeField()

    is_break = models.BooleanField(default=False)

    class Meta:
        ordering = ["academic_year", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "sequence"],
                name="unique_period_sequence_per_year",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.start_time:%H:%M}-{self.end_time:%H:%M})"


class TimetableEntry(models.Model):
    class Weekday(models.IntegerChoices):
        MONDAY = 1, "Monday"
        TUESDAY = 2, "Tuesday"
        WEDNESDAY = 3, "Wednesday"
        THURSDAY = 4, "Thursday"
        FRIDAY = 5, "Friday"
        SATURDAY = 6, "Saturday"

    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name="timetable",
    )

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="timetable",
        null=True,
        blank=True,
    )

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="timetable",
    )

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        related_name="timetable",
        null=True,
        blank=True,
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        related_name="timetable",
        null=True,
        blank=True,
    )

    period = models.ForeignKey(
        Period,
        on_delete=models.CASCADE,
        related_name="timetable",
    )

    weekday = models.IntegerField(choices=Weekday.choices)

    # Mirrors section_id, or 0 when there is none. A unique constraint cannot
    # span a nullable column portably: SQL treats NULL as distinct from NULL,
    # so an unsectioned class could be double-booked. The obvious fix - a
    # conditional constraint - is not available, because MySQL does not support
    # them and Django silently drops them there (models.W036), leaving the rule
    # unenforced on the production database. A non-null mirror needs no
    # condition and behaves identically everywhere.
    section_key = models.PositiveIntegerField(editable=False, default=0)

    class Meta:
        ordering = ["weekday", "period__sequence"]
        indexes = [
            models.Index(fields=["teacher", "weekday"]),
            models.Index(fields=["classroom", "weekday"]),
        ]
        constraints = [
            # A class cannot sit two subjects at once.
            models.UniqueConstraint(
                fields=["classroom", "section_key", "weekday", "period"],
                name="unique_slot_per_class",
            ),
            # Neither can a teacher be in two rooms, nor a room host two
            # classes. Enforced in the database rather than only in a form: a
            # double-booked teacher found on the first day of term is not a
            # recoverable mistake, and forms are not the only writer.
            #
            # No condition needed here: NULL semantics do the right thing by
            # themselves. Rows with no teacher never collide with each other,
            # which is correct, while two rows naming the same teacher do.
            models.UniqueConstraint(
                fields=["teacher", "weekday", "period"],
                name="unique_slot_per_teacher",
            ),
            models.UniqueConstraint(
                fields=["room", "weekday", "period"],
                name="unique_slot_per_room",
            ),
        ]

    def save(self, *args, **kwargs):
        self.section_key = self.section_id or 0
        if "update_fields" in kwargs and kwargs["update_fields"] is not None:
            # Otherwise a targeted save of "section" would leave the mirror
            # stale and the constraint guarding the wrong value.
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"section_key"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_weekday_display()} {self.period.name}: {self.subject.name}"
