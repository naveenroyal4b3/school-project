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

    class Meta:
        ordering = ["weekday", "period__sequence"]
        indexes = [
            models.Index(fields=["teacher", "weekday"]),
            models.Index(fields=["classroom", "weekday"]),
        ]
        constraints = [
            # A class cannot be in two places at once. Split in two because
            # SQL treats NULL as distinct from NULL, so a single constraint
            # over a nullable section would let an unsectioned class be
            # double-booked without complaint.
            models.UniqueConstraint(
                fields=["classroom", "section", "weekday", "period"],
                condition=models.Q(section__isnull=False),
                name="unique_slot_per_class_section",
            ),
            models.UniqueConstraint(
                fields=["classroom", "weekday", "period"],
                condition=models.Q(section__isnull=True),
                name="unique_slot_per_class",
            ),
            # Neither can a teacher. Enforced in the database rather than only
            # in a form: a double-booked teacher found on the first day of term
            # is not a recoverable mistake, and forms are not the only writer.
            models.UniqueConstraint(
                fields=["teacher", "weekday", "period"],
                condition=models.Q(teacher__isnull=False),
                name="unique_slot_per_teacher",
            ),
            models.UniqueConstraint(
                fields=["room", "weekday", "period"],
                condition=models.Q(room__isnull=False),
                name="unique_slot_per_room",
            ),
        ]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.period.name}: {self.subject.name}"
