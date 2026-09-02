import secrets

from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import User

from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    """A student and their sign-in account, created together.

    The account used to be a required foreign key the caller had to supply,
    which meant an admin had to create the user in Django admin first and then
    come back - and nothing in the API listed the accounts to choose from. A
    school adding a pupil should not have to visit two places, so the account is
    created here from the same form.
    """

    # Read side.
    student_name = serializers.CharField(source="user.get_full_name", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    classroom_name = serializers.CharField(source="classroom.name", read_only=True)
    guardian_name = serializers.CharField(
        source="parent.user.get_full_name", read_only=True
    )

    # Write side. Named apart from the read-only fields above so DRF does not
    # have to resolve one name to two different behaviours.
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    new_username = serializers.CharField(write_only=True, required=False)
    new_email = serializers.EmailField(write_only=True, required=False)
    phone_number = serializers.CharField(
        write_only=True, required=False, allow_blank=True
    )

    # Returned once, on creation, so the office can hand it to the student.
    # Never stored in readable form and never returned again.
    temporary_password = serializers.CharField(read_only=True)

    class Meta:
        model = Student
        fields = "__all__"
        # Supplied by the server on create, or left alone on update.
        read_only_fields = ["user", "organization"]

    def validate_new_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is already taken.")
        return value

    def validate_new_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("That email address is already in use.")
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get("new_username"):
            raise serializers.ValidationError(
                {"new_username": "A username is required to create the student's account."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Create the account and the student as one unit.

        Atomic: a student row without its account, or an orphan account with no
        student, would both need manual repair in the database.
        """

        account_fields = {
            "username": validated_data.pop("new_username"),
            "email": validated_data.pop("new_email", ""),
            "first_name": validated_data.pop("first_name", ""),
            "last_name": validated_data.pop("last_name", ""),
            "phone_number": validated_data.pop("phone_number", "") or None,
        }

        request = self.context.get("request")
        organization = validated_data.get("organization") or (
            request.user.organization if request else None
        )

        # A generated password rather than a fixed default, so a school that
        # forgets to change it is not left with every pupil sharing one.
        password = secrets.token_urlsafe(9)

        user = User(
            **account_fields,
            role=User.Role.STUDENT,
            organization=organization,
        )
        user.set_password(password)
        user.save()

        validated_data["organization"] = organization
        student = Student.objects.create(user=user, **validated_data)
        student.temporary_password = password
        return student

    @transaction.atomic
    def update(self, instance, validated_data):
        """Editing a student may also edit their account's name and contact."""

        user = instance.user
        touched = []
        for field, source in (
            ("first_name", "first_name"),
            ("last_name", "last_name"),
            ("new_email", "email"),
            ("phone_number", "phone_number"),
        ):
            if field in validated_data:
                value = validated_data.pop(field)
                setattr(user, source, value or (None if source == "phone_number" else ""))
                touched.append(source)

        validated_data.pop("new_username", None)  # usernames are not reassigned
        if touched:
            user.save(update_fields=touched)

        return super().update(instance, validated_data)
