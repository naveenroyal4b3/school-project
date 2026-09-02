"""Populate the database with a small, coherent demo dataset.

Written for the project document's final demonstration: one command produces a
college with staff, students, a bus on a route, attendance, fees and results,
so every screen has something to show.

Idempotent - re-running updates the same records instead of duplicating them.
"""

import datetime
import random
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academics.models import AcademicYear, ClassRoom, Course, Department, Section, Subject
from apps.accounts.models import User
from apps.attendance.models import Attendance, StudentQRCode
from apps.examinations.models import Exam, ExamSchedule, Result
from apps.fees.models import FeePayment, FeeStructure
from apps.organizations.models import Organization
from apps.parents.models import Parent
from apps.students.models import Student
from apps.teachers.models import Teacher
from apps.transport.models import Bus, BusLocation, Driver, Route, RouteStop, StudentTransport

PASSWORD = "Demo!Pass2026"


class Command(BaseCommand):
    help = "Create demo data for the Smart Student Management System."

    def add_arguments(self, parser):
        parser.add_argument(
            "--students",
            type=int,
            default=12,
            help="How many students to create (default 12).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(2026)  # reproducible demos
        count = options["students"]

        org, _ = Organization.objects.update_or_create(
            organization_code="DEMO",
            defaults={
                "organization_name": "Demo Public School",
                "organization_type": "School",
                "address": "12 Campus Road",
                "city": "Bengaluru",
                "state": "Karnataka",
                "country": "India",
                "pincode": "560001",
                "phone": "0801234567",
                "email": "office@demoschool.test",
                "subscription_start": datetime.date(2026, 6, 1),
                "subscription_end": datetime.date(2027, 5, 31),
            },
        )

        admin = self._user("admin", User.Role.ORGANIZATION_ADMIN, org, "Asha", "Rao")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save(update_fields=["is_staff", "is_superuser"])

        # --- Academics -----------------------------------------------------
        department, _ = Department.objects.update_or_create(
            organization=org, code="SCI", defaults={"name": "Science"}
        )
        Course.objects.update_or_create(
            department=department, code="PCM", defaults={"name": "Physics Chemistry Maths"}
        )

        year, _ = AcademicYear.objects.update_or_create(
            organization=org,
            name="2026-27",
            defaults={
                "start_date": datetime.date(2026, 6, 1),
                "end_date": datetime.date(2027, 4, 30),
            },
        )
        classroom, _ = ClassRoom.objects.update_or_create(
            academic_year=year, name="Grade 10"
        )
        Section.objects.update_or_create(classroom=classroom, name="A", defaults={"capacity": 40})
        subjects = [
            Subject.objects.update_or_create(
                classroom=classroom, code=code, defaults={"name": name}
            )[0]
            for code, name in [("MTH", "Mathematics"), ("SCI", "Science"), ("ENG", "English")]
        ]

        # --- Faculty -------------------------------------------------------
        for i, (first, last) in enumerate([("Ravi", "Kumar"), ("Meera", "Nair")], start=1):
            Teacher.objects.update_or_create(
                user=self._user(f"teacher{i}", User.Role.TEACHER, org, first, last),
                defaults={
                    "organization": org,
                    "employee_id": f"EMP-{i:03d}",
                    "qualification": "M.Sc B.Ed",
                    "experience": 5 + i,
                },
            )

        # --- Transport -----------------------------------------------------
        driver = Driver.objects.update_or_create(
            user=self._user("driver1", User.Role.DRIVER, org, "Suresh", "Patil"),
            defaults={
                "organization": org,
                "license_number": "KA-DL-2026-001",
                "license_expiry": datetime.date(2030, 3, 31),
                "experience_years": 8,
            },
        )[0]

        route = Route.objects.update_or_create(
            organization=org,
            code="RT-01",
            defaults={
                "name": "North Loop",
                "start_point": "Depot",
                "end_point": "Demo Public School",
                "distance_km": Decimal("14.50"),
                "estimated_duration_minutes": 45,
            },
        )[0]

        stops = []
        for seq, (name, lat, lng) in enumerate(
            [
                ("Depot", "12.985000", "77.590000"),
                ("Market Square", "12.975000", "77.595000"),
                ("Lake View", "12.968000", "77.601000"),
                ("School Gate", "12.960000", "77.610000"),
            ],
            start=1,
        ):
            stops.append(
                RouteStop.objects.update_or_create(
                    route=route,
                    sequence=seq,
                    defaults={"name": name, "latitude": lat, "longitude": lng},
                )[0]
            )

        bus = Bus.objects.update_or_create(
            registration_number="KA-01-AB-1234",
            defaults={
                "organization": org,
                "model": "Tata Starbus",
                "capacity": 40,
                "driver": driver,
                "route": route,
            },
        )[0]
        BusLocation.objects.create(
            bus=bus, latitude="12.975000", longitude="77.595000", speed_kmph="32.50"
        )

        # --- Fees ----------------------------------------------------------
        fee = FeeStructure.objects.update_or_create(
            organization=org,
            name="Term 1 Tuition",
            defaults={
                "academic_year": year,
                "classroom": classroom,
                "amount": Decimal("15000.00"),
                "frequency": FeeStructure.Frequency.QUARTERLY,
                "due_date": datetime.date(2026, 9, 30),
            },
        )[0]

        # --- Exams ---------------------------------------------------------
        exam = Exam.objects.update_or_create(
            organization=org,
            name="Midterm 2026",
            defaults={
                "academic_year": year,
                "exam_type": Exam.ExamType.MIDTERM,
                "start_date": datetime.date(2026, 10, 5),
                "end_date": datetime.date(2026, 10, 12),
                "is_published": True,
            },
        )[0]
        schedules = [
            ExamSchedule.objects.update_or_create(
                exam=exam,
                subject=subject,
                classroom=classroom,
                defaults={
                    "exam_date": datetime.date(2026, 10, 5 + i),
                    "start_time": datetime.time(9, 30),
                    "end_time": datetime.time(12, 30),
                },
            )[0]
            for i, subject in enumerate(subjects)
        ]

        # --- Students, guardians and their records --------------------------
        names = [
            ("Aarav", "Sharma"), ("Diya", "Menon"), ("Kabir", "Iyer"), ("Ananya", "Bose"),
            ("Vihaan", "Reddy"), ("Isha", "Kulkarni"), ("Arjun", "Desai"), ("Sara", "Khan"),
            ("Rohan", "Gupta"), ("Nisha", "Verma"), ("Dev", "Joshi"), ("Tara", "Pillai"),
        ]

        created = 0
        for i in range(1, count + 1):
            first, last = names[(i - 1) % len(names)]

            parent = Parent.objects.update_or_create(
                user=self._user(
                    f"parent{i}", User.Role.PARENT, org, f"{first}'s", "Guardian",
                    phone_number=f"99000{i:05d}",
                ),
                defaults={
                    "organization": org,
                    "relationship": "Father" if i % 2 else "Mother",
                },
            )[0]

            student = Student.objects.update_or_create(
                admission_no=f"ADM-2026-{i:03d}",
                defaults={
                    "user": self._user(f"student{i}", User.Role.STUDENT, org, first, last),
                    "organization": org,
                    "academic_year": year,
                    "classroom": classroom,
                    "parent": parent,
                    "roll_number": f"R-{i:03d}",
                    "date_of_birth": datetime.date(2010, 1 + (i % 12), 1 + (i % 27)),
                    "gender": "Male" if i % 2 else "Female",
                    "address": f"{i} Demo Street, Bengaluru",
                    "admission_date": datetime.date(2026, 6, 1),
                },
            )[0]
            created += 1

            StudentQRCode.objects.get_or_create(student=student)
            StudentTransport.objects.update_or_create(
                student=student,
                defaults={"bus": bus, "pickup_stop": stops[i % len(stops)]},
            )

            # Two weeks of attendance, mostly present.
            for day_offset in range(14):
                day = datetime.date(2026, 9, 1) + datetime.timedelta(days=day_offset)
                if day.weekday() >= 5:
                    continue
                Attendance.objects.update_or_create(
                    student=student,
                    subject=None,
                    date=day,
                    defaults={
                        "status": random.choices(
                            [
                                Attendance.Status.PRESENT,
                                Attendance.Status.ABSENT,
                                Attendance.Status.LATE,
                            ],
                            weights=[85, 10, 5],
                        )[0],
                        "marked_by": admin,
                    },
                )

            if not student.fee_payments.exists():
                FeePayment.objects.create(
                    student=student,
                    fee_structure=fee,
                    amount_paid=Decimal(random.choice(["15000.00", "7500.00", "10000.00"])),
                    payment_method=random.choice(
                        [FeePayment.Method.UPI, FeePayment.Method.CASH, FeePayment.Method.CARD]
                    ),
                )

            for schedule in schedules:
                Result.objects.update_or_create(
                    student=student,
                    exam_schedule=schedule,
                    defaults={"marks_obtained": Decimal(random.randint(28, 98))},
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded '{org.organization_name}' with {created} students, "
                f"{len(subjects)} subjects, 1 bus on route {route.code}."
            )
        )
        self.stdout.write(f"  Admin login:   admin / {PASSWORD}")
        self.stdout.write(f"  Teacher login: teacher1 / {PASSWORD}")
        self.stdout.write(f"  Student login: student1 / {PASSWORD}")

    def _user(self, username, role, organization, first="", last="", **extra):
        user, created = User.objects.update_or_create(
            username=username,
            defaults={
                "email": f"{username}@demoschool.test",
                "role": role,
                "organization": organization,
                "first_name": first,
                "last_name": last,
                **extra,
            },
        )
        if created:
            user.set_password(PASSWORD)
            user.save(update_fields=["password"])
        return user
