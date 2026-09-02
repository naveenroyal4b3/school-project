from rest_framework import serializers

from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="user.get_full_name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    guardian_name = serializers.CharField(
        source="parent.user.get_full_name", read_only=True
    )

    class Meta:
        model = Student
        fields = "__all__"
