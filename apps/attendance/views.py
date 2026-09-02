from django.db import transaction
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.response import Response

from apps.common.mixins import OrganizationScopedMixin, RowLevelScopedMixin
from apps.common.permissions import (
    IsAdmin,
    IsAdminOrReadOnly,
    IsDriverOrAdmin,
    IsFacultyOrAdmin,
)
from apps.students.models import Student
from apps.transport.models import Bus, Trip

from .models import Attendance, BusAttendance, CampusScan, StudentQRCode
from .qr import render_png
from .serializers import (
    AttendanceSerializer,
    BulkAttendanceSerializer,
    BusAttendanceSerializer,
    CampusScanSerializer,
    ScanSerializer,
    StudentQRCodeSerializer,
)
from .services import record_bus_scan, record_campus_scan


class AttendanceListCreateView(RowLevelScopedMixin, generics.ListCreateAPIView):
    queryset = Attendance.objects.select_related("student").all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "student__organization"
    student_path = "student"

    def get_queryset(self):
        queryset = super().get_queryset()

        student = self.request.query_params.get("student")
        if student:
            queryset = queryset.filter(student_id=student)

        date_from = self.request.query_params.get("from")
        if date_from:
            queryset = queryset.filter(date__gte=date_from)

        date_to = self.request.query_params.get("to")
        if date_to:
            queryset = queryset.filter(date__lte=date_to)

        return queryset

    def perform_create(self, serializer):
        # Recorded server-side: who marked the register is an audit fact and
        # must not be settable by the client.
        serializer.save(marked_by=self.request.user)


class AttendanceDetailView(RowLevelScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Attendance.objects.select_related("student").all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "student__organization"
    student_path = "student"


class BulkAttendanceView(generics.GenericAPIView):
    """Mark a whole class at once.

    Applied in a single transaction so a bad row rejects the entire roll call
    rather than leaving half a class marked.
    """

    serializer_class = BulkAttendanceSerializer
    permission_classes = [IsFacultyOrAdmin]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        visible_students = Student.objects.all()
        user = request.user
        if not user.is_superuser and user.organization_id is not None:
            visible_students = visible_students.filter(organization_id=user.organization_id)

        created, errors = [], []
        with transaction.atomic():
            for row in data["records"]:
                student = visible_students.filter(pk=row.get("student")).first()
                if student is None:
                    errors.append({"student": row.get("student"), "error": "not found"})
                    continue

                record, _ = Attendance.objects.update_or_create(
                    student=student,
                    subject_id=data.get("subject"),
                    date=data["date"],
                    defaults={
                        "status": row.get("status", Attendance.Status.PRESENT),
                        "remarks": row.get("remarks"),
                        "marked_by": user,
                    },
                )
                created.append(record.id)

            if errors:
                transaction.set_rollback(True)
                return Response(
                    {"errors": errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(
            {"marked": len(created), "attendance_ids": created},
            status=status.HTTP_201_CREATED,
        )


class StudentQRCodeListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    """Issued ID cards.

    Admin-only, including reads: the code on a card is a credential, and anyone
    holding one can have attendance recorded against that student. Listing them
    to classmates would hand out the whole school's cards.
    """

    queryset = StudentQRCode.objects.select_related("student__user").all()
    serializer_class = StudentQRCodeSerializer
    permission_classes = [IsAdmin]
    organization_path = "student__organization"


class StudentQRCodeDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = StudentQRCode.objects.select_related("student__user").all()
    serializer_class = StudentQRCodeSerializer
    permission_classes = [IsAdmin]
    organization_path = "student__organization"


class StudentQRCodeImageView(OrganizationScopedMixin, generics.GenericAPIView):
    """The scannable QR for one card, as a PNG.

    Rendered on demand rather than stored, so reissuing a card cannot leave a
    stale image behind. Scoped like every other view - a card image identifies a
    student, so it must not be readable across colleges.
    """

    queryset = StudentQRCode.objects.all()
    serializer_class = StudentQRCodeSerializer
    permission_classes = [IsAdmin]
    organization_path = "student__organization"

    def get(self, request, *args, **kwargs):
        qr = self.get_object()
        response = HttpResponse(render_png(str(qr.code)), content_type="image/png")
        response["Cache-Control"] = "private, max-age=3600"
        return response


class IssueQRCodesView(generics.GenericAPIView):
    """Issue a card to every student in the college that does not have one.

    Idempotent - a student who already holds an active card keeps it, so this
    can be run after each admission intake without reissuing the whole school.
    """

    serializer_class = StudentQRCodeSerializer
    permission_classes = [IsAdmin]

    def post(self, request, *args, **kwargs):
        students = Student.objects.filter(is_active=True)

        user = request.user
        if not user.is_superuser and user.organization_id is not None:
            students = students.filter(organization_id=user.organization_id)

        issued = [
            StudentQRCode.objects.get_or_create(student=student)[0]
            for student in students.filter(qr_code__isnull=True)
        ]

        return Response(
            {
                "issued": len(issued),
                "cards": StudentQRCodeSerializer(issued, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )


class BusAttendanceListView(RowLevelScopedMixin, generics.ListAPIView):
    queryset = BusAttendance.objects.select_related("student", "bus").all()
    serializer_class = BusAttendanceSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"
    student_path = "student"


class CampusScanListView(RowLevelScopedMixin, generics.ListAPIView):
    queryset = CampusScan.objects.select_related("student", "attendance").all()
    serializer_class = CampusScanSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"
    student_path = "student"


class ScanView(generics.GenericAPIView):
    """POST /api/attendance/scan/ - record an ID card scan.

    A CAMPUS IN scan marks the student present for the day automatically; a BUS
    scan records a boarding. Both alert the guardian.

    The QR code identifies the student, so the caller never supplies a student
    id: accepting one would let any reader record attendance for any student.
    """

    serializer_class = ScanSerializer
    permission_classes = [IsDriverOrAdmin]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qr = (
            StudentQRCode.objects.select_related(
                "student__organization", "student__user", "student__parent__user"
            )
            .filter(code=data["code"], is_active=True)
            .first()
        )

        user = request.user
        # An unknown card and another college's card return the same 404, so the
        # endpoint cannot be used to probe which codes exist.
        if qr is None or (
            not user.is_superuser
            and user.organization_id is not None
            and qr.student.organization_id != user.organization_id
        ):
            return Response(
                {"error": "Unknown or inactive ID card."},
                status=status.HTTP_404_NOT_FOUND,
            )

        student = qr.student

        if data["context"] == ScanSerializer.Context.BUS:
            record = record_bus_scan(
                student,
                data["scan_type"],
                bus=Bus.objects.filter(pk=data.get("bus")).first(),
                trip=Trip.objects.filter(pk=data.get("trip")).first(),
                latitude=data.get("latitude"),
                longitude=data.get("longitude"),
            )
            return Response(
                {
                    "context": "BUS",
                    "student": student.admission_no,
                    "student_name": student.user.get_full_name(),
                    "scan": BusAttendanceSerializer(record).data,
                },
                status=status.HTTP_201_CREATED,
            )

        scan, attendance = record_campus_scan(
            student, data["scan_type"], device_id=data.get("device_id") or None
        )

        return Response(
            {
                "context": "CAMPUS",
                "student": student.admission_no,
                "student_name": student.user.get_full_name(),
                "scan": CampusScanSerializer(scan).data,
                "attendance": AttendanceSerializer(attendance).data if attendance else None,
            },
            status=status.HTTP_201_CREATED,
        )
