from rest_framework import serializers

from .models import Exam, ExamSchedule, Result


class ExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = "__all__"


class ExamScheduleSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    exam_name = serializers.CharField(source="exam.name", read_only=True)

    class Meta:
        model = ExamSchedule
        fields = "__all__"

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start and end and end <= start:
            raise serializers.ValidationError("end_time must be after start_time.")

        max_marks = attrs.get("max_marks")
        passing = attrs.get("passing_marks")
        if max_marks is not None and passing is not None and passing > max_marks:
            raise serializers.ValidationError("passing_marks cannot exceed max_marks.")

        return attrs


class ResultSerializer(serializers.ModelSerializer):
    admission_no = serializers.CharField(source="student.admission_no", read_only=True)
    subject_name = serializers.CharField(
        source="exam_schedule.subject.name", read_only=True
    )
    exam = serializers.IntegerField(source="exam_schedule.exam_id", read_only=True)
    exam_name = serializers.CharField(source="exam_schedule.exam.name", read_only=True)
    percentage = serializers.DecimalField(
        max_digits=6, decimal_places=2, read_only=True
    )

    class Meta:
        model = Result
        fields = "__all__"
        read_only_fields = ["grade", "is_pass"]

    def validate(self, attrs):
        schedule = attrs.get("exam_schedule") or getattr(self.instance, "exam_schedule", None)
        marks = attrs.get("marks_obtained")

        if schedule and marks is not None and marks > schedule.max_marks:
            raise serializers.ValidationError(
                f"marks_obtained cannot exceed max_marks ({schedule.max_marks})."
            )

        return attrs
