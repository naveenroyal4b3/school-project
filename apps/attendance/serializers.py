from rest_framework import serializers

from .models import Attendance, BusAttendance, StudentQRCode


class AttendanceSerializer(serializers.ModelSerializer):
    admission_no = serializers.CharField(source="student.admission_no", read_only=True)

    class Meta:
        model = Attendance
        fields = "__all__"
        read_only_fields = ["marked_by"]


class BulkAttendanceSerializer(serializers.Serializer):
    """Marking a whole class in one request.

    Faculty take a roll call for thirty students at once; sending thirty
    separate POSTs would be slow over a phone connection and could half-apply.
    """

    date = serializers.DateField()
    subject = serializers.IntegerField(required=False, allow_null=True)
    records = serializers.ListField(child=serializers.DictField(), allow_empty=False)


class StudentQRCodeSerializer(serializers.ModelSerializer):
    admission_no = serializers.CharField(source="student.admission_no", read_only=True)

    class Meta:
        model = StudentQRCode
        fields = "__all__"


class BusAttendanceSerializer(serializers.ModelSerializer):
    admission_no = serializers.CharField(source="student.admission_no", read_only=True)

    class Meta:
        model = BusAttendance
        fields = "__all__"
        read_only_fields = ["scanned_at"]


class ScanSerializer(serializers.Serializer):
    """Input for POST /api/attendance/scan/ - the document's ID card scan."""

    code = serializers.CharField(max_length=64)
    scan_type = serializers.ChoiceField(choices=BusAttendance.ScanType.choices)
    bus = serializers.IntegerField(required=False, allow_null=True)
    trip = serializers.IntegerField(required=False, allow_null=True)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
