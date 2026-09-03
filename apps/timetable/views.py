from django.db import IntegrityError
from rest_framework import generics, status
from rest_framework.response import Response

from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsAdminOrReadOnly, IsFacultyOrAdmin

from .models import Period, Room, TimetableEntry
from .serializers import (
    PeriodSerializer,
    RoomSerializer,
    TimetableEntrySerializer,
)

# Every table hangs off AcademicYear, which is where the organization lives.
YEAR_PATH = "academic_year__organization"


class RoomListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = YEAR_PATH


class RoomDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = YEAR_PATH


class PeriodListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Period.objects.all()
    serializer_class = PeriodSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = YEAR_PATH


class PeriodDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Period.objects.all()
    serializer_class = PeriodSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = YEAR_PATH


class ClashReportingMixin:
    """Turn a database clash into a message a timetabler can act on.

    The unique constraints are the real guard, but their raw IntegrityError
    says only that some constraint failed. Naming which one - and who is
    double-booked - is the difference between a usable error and a shrug.
    """

    CLASH_MESSAGES = {
        "unique_slot_per_teacher": "That teacher is already teaching in this period.",
        "unique_slot_per_class": "That class already has a subject in this period.",
        "unique_slot_per_class_section": "That section already has a subject in this period.",
        "unique_slot_per_room": "That room is already in use in this period.",
    }

    def handle_exception(self, exc):
        if isinstance(exc, IntegrityError):
            message = next(
                (text for name, text in self.CLASH_MESSAGES.items() if name in str(exc)),
                "That slot is already taken.",
            )
            return Response({"detail": message}, status=status.HTTP_409_CONFLICT)
        return super().handle_exception(exc)


class TimetableEntryListCreateView(
    ClashReportingMixin, OrganizationScopedMixin, generics.ListCreateAPIView
):
    queryset = TimetableEntry.objects.select_related(
        "subject", "teacher__user", "room", "period", "classroom", "section"
    ).all()
    serializer_class = TimetableEntrySerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "classroom__academic_year__organization"

    def get_queryset(self):
        queryset = super().get_queryset()

        for field in ("classroom", "section", "teacher", "weekday"):
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})

        return queryset


class TimetableEntryDetailView(
    ClashReportingMixin, OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView
):
    queryset = TimetableEntry.objects.select_related(
        "subject", "teacher__user", "room", "period"
    ).all()
    serializer_class = TimetableEntrySerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "classroom__academic_year__organization"


class TeacherScheduleView(OrganizationScopedMixin, generics.ListAPIView):
    """One teacher's week - the "Teacher Schedule" in the architecture diagram."""

    queryset = TimetableEntry.objects.select_related(
        "subject", "room", "period", "classroom", "section"
    ).all()
    serializer_class = TimetableEntrySerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "classroom__academic_year__organization"

    def get_queryset(self):
        return super().get_queryset().filter(teacher_id=self.kwargs["teacher_id"])
