from rest_framework import serializers

from .models import Attendance, BusAttendance, CampusScan, StudentQRCode


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
    student_name = serializers.CharField(
        source="student.user.get_full_name", read_only=True
    )
    image_url = serializers.SerializerMethodField()
    card_url = serializers.SerializerMethodField()

    class Meta:
        model = StudentQRCode
        fields = "__all__"

    def get_image_url(self, obj):
        return f"/api/attendance/qr-codes/{obj.pk}/image/"

    def get_card_url(self, obj):
        return f"/id-card/{obj.student_id}/"


class BusAttendanceSerializer(serializers.ModelSerializer):
    admission_no = serializers.CharField(source="student.admission_no", read_only=True)

    class Meta:
        model = BusAttendance
        fields = "__all__"
        read_only_fields = ["scanned_at"]


class CampusScanSerializer(serializers.ModelSerializer):
    admission_no = serializers.CharField(source="student.admission_no", read_only=True)

    class Meta:
        model = CampusScan
        fields = "__all__"
        read_only_fields = ["scanned_at", "attendance"]


class ScanSerializer(serializers.Serializer):
    """Input for POST /api/attendance/scan/ - the ID card scan.

    One endpoint serves both readers the document describes. ``context`` says
    which: CAMPUS marks the day's academic attendance automatically, BUS records
    a boarding. It defaults to CAMPUS because that is the common case, and a
    fixed gate reader can then post nothing but the code.
    """

    class Context:
        CAMPUS = "CAMPUS"
        BUS = "BUS"

    code = serializers.CharField(max_length=64)
    scan_type = serializers.ChoiceField(
        choices=[("IN", "In"), ("OUT", "Out")], default="IN"
    )
    context = serializers.ChoiceField(
        choices=[(Context.CAMPUS, "Campus"), (Context.BUS, "Bus")],
        default=Context.CAMPUS,
    )
    device_id = serializers.CharField(max_length=50, required=False, allow_blank=True)

    # Bus scans only.
    bus = serializers.IntegerField(required=False, allow_null=True)
    trip = serializers.IntegerField(required=False, allow_null=True)
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, required=False, allow_null=True
    )
