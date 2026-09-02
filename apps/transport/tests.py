import datetime

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.testing import (
    make_admin,
    make_driver_user,
    make_organization,
    make_student,
)

from .models import Bus, BusLocation, Driver, Route, Trip


class TransportFixtureMixin:
    def build_fixture(self, code="ORGA", name="School A", suffix=""):
        org = make_organization(code, name)
        driver = Driver.objects.create(
            user=make_driver_user(org, f"driver{suffix or '1'}"),
            organization=org,
            license_number=f"LIC{suffix or '1'}",
            license_expiry=datetime.date(2030, 1, 1),
        )
        route = Route.objects.create(
            organization=org,
            name="North Loop",
            code=f"RT{suffix or '1'}",
            start_point="Depot",
            end_point="Campus",
        )
        bus = Bus.objects.create(
            organization=org,
            registration_number=f"KA01AB{suffix or '1'}",
            driver=driver,
            route=route,
        )
        return org, driver, route, bus


class TripLifecycleTests(TransportFixtureMixin, APITestCase):
    def setUp(self):
        self.org, self.driver, self.route, self.bus = self.build_fixture()
        self.trip = Trip.objects.create(bus=self.bus, driver=self.driver, route=self.route)

    def test_driver_starts_and_ends_a_trip(self):
        self.client.force_authenticate(self.driver.user)

        started = self.client.post(reverse("trip-start", args=[self.trip.id]))
        self.assertEqual(started.status_code, status.HTTP_200_OK)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, Trip.Status.IN_PROGRESS)
        self.assertIsNotNone(self.trip.started_at)

        ended = self.client.post(reverse("trip-end", args=[self.trip.id]))
        self.assertEqual(ended.status_code, status.HTTP_200_OK)
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, Trip.Status.COMPLETED)
        self.assertIsNotNone(self.trip.ended_at)

    def test_starting_twice_does_not_reset_the_clock(self):
        self.client.force_authenticate(self.driver.user)

        self.client.post(reverse("trip-start", args=[self.trip.id]))
        self.trip.refresh_from_db()
        first_start = self.trip.started_at

        self.client.post(reverse("trip-start", args=[self.trip.id]))
        self.trip.refresh_from_db()

        self.assertEqual(self.trip.started_at, first_start)

    def test_a_student_may_not_start_a_trip(self):
        student = make_student(self.org)
        self.client.force_authenticate(student.user)

        response = self.client.post(reverse("trip-start", args=[self.trip.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_a_driver_cannot_touch_another_colleges_trip(self):
        _, other_driver, _, _ = self.build_fixture("ORGB", "School B", "2")
        self.client.force_authenticate(other_driver.user)

        response = self.client.post(reverse("trip-start", args=[self.trip.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class LiveTrackingTests(TransportFixtureMixin, APITestCase):
    def setUp(self):
        self.org, self.driver, self.route, self.bus = self.build_fixture()

    def test_tracking_returns_the_newest_ping_per_bus(self):
        BusLocation.objects.create(bus=self.bus, latitude="12.900000", longitude="77.500000")
        newest = BusLocation.objects.create(
            bus=self.bus, latitude="12.950000", longitude="77.600000", speed_kmph="40.00"
        )
        newest.refresh_from_db()  # the in-memory instance still holds the input strings

        self.client.force_authenticate(make_admin(self.org))
        response = self.client.get(reverse("live-tracking"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["latitude"], newest.latitude)

    def test_a_bus_with_no_pings_still_appears(self):
        self.client.force_authenticate(make_admin(self.org))
        response = self.client.get(reverse("live-tracking"))

        self.assertEqual(len(response.data), 1)
        self.assertIsNone(response.data[0]["latitude"])

    def test_students_may_watch_for_their_own_bus(self):
        student = make_student(self.org)
        self.client.force_authenticate(student.user)

        self.assertEqual(
            self.client.get(reverse("live-tracking")).status_code,
            status.HTTP_200_OK,
        )

    def test_tracking_does_not_reveal_another_colleges_fleet(self):
        other_org, _, _, _ = self.build_fixture("ORGB", "School B", "2")

        self.client.force_authenticate(make_admin(other_org, "admin_b"))
        response = self.client.get(reverse("live-tracking"))

        registrations = [row["registration_number"] for row in response.data]
        self.assertNotIn(self.bus.registration_number, registrations)


class BusManagementTests(TransportFixtureMixin, APITestCase):
    def test_only_admins_create_buses(self):
        org, driver, _, _ = self.build_fixture()

        self.client.force_authenticate(driver.user)
        self.assertEqual(
            self.client.post(reverse("bus-list"), {}).status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.client.force_authenticate(make_admin(org))
        response = self.client.post(
            reverse("bus-list"),
            {"organization": org.id, "registration_number": "KA01ZZ9", "capacity": 30},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
