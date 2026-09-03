from rest_framework import serializers

from .models import Period, Room, TimetableEntry


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = "__all__"


class PeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Period
        fields = "__all__"

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start and end and end <= start:
            raise serializers.ValidationError("end_time must be after start_time.")
        return attrs


class TimetableEntrySerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_name = serializers.CharField(
        source="teacher.user.get_full_name", read_only=True
    )
    room_name = serializers.CharField(source="room.name", read_only=True)
    period_name = serializers.CharField(source="period.name", read_only=True)
    weekday_label = serializers.CharField(source="get_weekday_display", read_only=True)
    starts_at = serializers.TimeField(source="period.start_time", read_only=True)
    ends_at = serializers.TimeField(source="period.end_time", read_only=True)

    class Meta:
        model = TimetableEntry
        fields = "__all__"
        # DRF derives validators from the model's unique constraints and runs
        # them before validate(), so its generic "the fields teacher, weekday,
        # period must make a unique set" would win over the message below. The
        # database constraint remains the guarantee; this only decides which
        # explanation the timetabler reads.
        validators = []

    def validate(self, attrs):
        """Catch a clash before the database does, so the message names the
        conflicting lesson rather than just reporting a failed constraint."""

        def value(field):
            return attrs.get(field) or getattr(self.instance, field, None)

        period, weekday = value("period"), value("weekday")
        teacher, room = value("teacher"), value("room")

        if not (period and weekday):
            return attrs

        clashes = TimetableEntry.objects.filter(period=period, weekday=weekday)
        if self.instance:
            clashes = clashes.exclude(pk=self.instance.pk)

        if teacher:
            existing = clashes.filter(teacher=teacher).first()
            if existing:
                raise serializers.ValidationError({
                    "teacher": (
                        f"Already teaching {existing.subject.name} to "
                        f"{existing.classroom.name} in this period."
                    )
                })

        if room:
            existing = clashes.filter(room=room).first()
            if existing:
                raise serializers.ValidationError({
                    "room": f"Already used by {existing.classroom.name} in this period."
                })

        classroom, section = value("classroom"), value("section")
        if classroom:
            existing = clashes.filter(classroom=classroom, section=section).first()
            if existing:
                raise serializers.ValidationError({
                    "classroom": (
                        f"This class already has {existing.subject.name} in "
                        "this period."
                    )
                })

        return attrs
