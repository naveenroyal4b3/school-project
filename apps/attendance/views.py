from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response

from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsAdminOrReadOnly, IsDriverOrAdmin, IsFacultyOrAdmin
from apps.notifications.models import Notification
from apps.notifications.services import notify_guardians
from apps.students.models import Student
from apps.transport.models import Bus, Trip

from .models import Attendance, BusAttendance, StudentQRCode
from .serializers import (
    AttendanceSerializer,
    BulkAttendanceSerializer,
    BusAttendanceSerializer,
    ScanSerializer,
    StudentQRCodeSerializer,
)


class AttendanceListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Attendance.objects.select_related("student").all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "student__organization"

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


class AttendanceDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Attendance.objects.select_related("student").all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsFacultyOrAdmin]
    organization_path = "student__organization"


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
    queryset = StudentQRCode.objects.select_related("student").all()
    serializer_class = StudentQRCodeSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"


class StudentQRCodeDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = StudentQRCode.objects.select_related("student").all()
    serializer_class = StudentQRCodeSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"


class BusAttendanceListView(OrganizationScopedMixin, generics.ListAPIView):
    queryset = BusAttendance.objects.select_related("student", "bus").all()
    serializer_class = BusAttendanceSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"


class ScanView(generics.GenericAPIView):
    """POST /api/attendance/scan/ - record a bus IN/OUT from an ID card scan.

    Drivers and admins may scan. The QR code identifies the student, so the
    caller never supplies a student id: accepting one would let a driver record
    attendance for any student in the college.
    """

    serializer_class = ScanSerializer
    permission_classes = [IsDriverOrAdmin]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qr = (
            StudentQRCode.objects.select_related("student__organization", "student__parent__user")
            .filter(code=data["code"], is_active=True)
            .first()
        )
        if qr is None:
            return Response(
                {"error": "Unknown or inactive ID card."},
                status=status.HTTP_404_NOT_FOUND,
            )

        student = qr.student

        user = request.user
        if (
            not user.is_superuser
            and user.organization_id is not None
            and student.organization_id != user.organization_id
        ):
            return Response(
                {"error": "Unknown or inactive ID card."},
                status=status.HTTP_404_NOT_FOUND,
            )

        record = BusAttendance.objects.create(
            student=student,
            bus=Bus.objects.filter(pk=data.get("bus")).first(),
            trip=Trip.objects.filter(pk=data.get("trip")).first(),
            scan_type=data["scan_type"],
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
        )

        verb = "boarded" if record.scan_type == BusAttendance.ScanType.IN else "got off"
        notify_guardians(
            student,
            title="Bus attendance",
            message=(
                f"{student.user.get_full_name() or student.user.username} "
                f"{verb} the bus at {record.scanned_at:%d %b %Y %H:%M}."
            ),
            notification_type=Notification.Type.TRANSPORT,
        )

        return Response(
            BusAttendanceSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )
