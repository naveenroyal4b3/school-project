from rest_framework import serializers
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "phone_number",
            "role",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = "__all__"


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