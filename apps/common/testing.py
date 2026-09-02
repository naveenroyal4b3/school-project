"""Object factories shared across the test suites.

Kept out of ``tests.py`` so every app can import them without importing another
app's test cases (which would run them twice).
"""

import datetime

from apps.accounts.models import User
from apps.organizations.models import Organization
from apps.parents.models import Parent
from apps.students.models import Student


def make_organization(code="ORG1", name="Test School"):
    return Organization.objects.create(
        organization_code=code,
        organization_name=name,
        organization_type="School",
        address="1 Test Road",
        city="Testville",
        state="TS",
        country="Testland",
        pincode="123456",
        phone="0000000000",
        email=f"{code.lower()}@example.test",
        subscription_start=datetime.date(2026, 1, 1),
        subscription_end=datetime.date(2027, 1, 1),
    )


def make_user(username, role=User.Role.STUDENT, organization=None, **extra):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="TestPass!2026",
        role=role,
        organization=organization,
        **extra,
    )


def make_parent(organization, username="parent1", phone="9999900001"):
    user = make_user(username, User.Role.PARENT, organization, phone_number=phone)
    return Parent.objects.create(user=user, organization=organization, relationship="Father")


def make_student(
    organization,
    username="student1",
    admission_no="ADM-1",
    roll_number="R-1",
    parent=None,
    classroom=None,
):
    return Student.objects.create(
        user=make_user(username, User.Role.STUDENT, organization),
        organization=organization,
        classroom=classroom,
        parent=parent,
        admission_no=admission_no,
        roll_number=roll_number,
        date_of_birth=datetime.date(2010, 5, 1),
        gender="Male",
        address="2 Test Lane",
        admission_date=datetime.date(2026, 6, 1),
    )


def make_admin(organization, username="admin1"):
    return make_user(username, User.Role.ORGANIZATION_ADMIN, organization)


def make_teacher_user(organization, username="teacher1"):
    return make_user(username, User.Role.TEACHER, organization)


def make_driver_user(organization, username="driver1"):
    return make_user(username, User.Role.DRIVER, organization)


def rows(response):
    """The records from a list response.

    List endpoints are paginated, so the payload is {count, next, previous,
    results}. Tests care about the records, not the envelope.
    """
    data = response.data
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data
