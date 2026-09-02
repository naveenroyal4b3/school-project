from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Public self-registration.

    "role" is deliberately absent: this endpoint is AllowAny, so accepting a
    role from the request body would let anyone register themselves as
    SUPER_ADMIN. Self-registered accounts always land on the default STUDENT
    role, and an admin promotes them afterwards.
    """

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User(**validated_data, role=User.Role.STUDENT)
        user.set_password(password)
        user.save()

        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # Explicit list: "__all__" leaked the password hash plus
        # is_superuser/is_staff/permissions in the register response.
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "role",
            "organization",
            "profile_image",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class OrganizationAdminSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "phone_number",
            "password",
            "organization",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User(
            **validated_data,
            role=User.Role.ORGANIZATION_ADMIN,
        )

        user.set_password(password)
        user.save()

        return user