from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.mixins import OrganizationScopedMixin, RowLevelScopedMixin
from apps.common.permissions import IsAdminOrReadOnly, IsDriverOrAdmin

from .models import Bus, BusLocation, Driver, Route, RouteStop, StudentTransport, Trip
from .serializers import (
    BusLocationSerializer,
    BusSerializer,
    DriverSerializer,
    RouteSerializer,
    RouteStopSerializer,
    StudentTransportSerializer,
    TripSerializer,
)


class DriverListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Driver.objects.select_related("user").all()
    serializer_class = DriverSerializer
    permission_classes = [IsAdminOrReadOnly]


class DriverDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Driver.objects.select_related("user").all()
    serializer_class = DriverSerializer
    permission_classes = [IsAdminOrReadOnly]


class RouteListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Route.objects.prefetch_related("stops").all()
    serializer_class = RouteSerializer
    permission_classes = [IsAdminOrReadOnly]


class RouteDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Route.objects.prefetch_related("stops").all()
    serializer_class = RouteSerializer
    permission_classes = [IsAdminOrReadOnly]


class RouteStopListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = RouteStop.objects.all()
    serializer_class = RouteStopSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "route__organization"


class RouteStopDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = RouteStop.objects.all()
    serializer_class = RouteStopSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "route__organization"


class BusListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Bus.objects.select_related("driver__user", "route").all()
    serializer_class = BusSerializer
    permission_classes = [IsAdminOrReadOnly]


class BusDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Bus.objects.select_related("driver__user", "route").all()
    serializer_class = BusSerializer
    permission_classes = [IsAdminOrReadOnly]


class StudentTransportListCreateView(RowLevelScopedMixin, generics.ListCreateAPIView):
    queryset = StudentTransport.objects.select_related("student", "bus").all()
    serializer_class = StudentTransportSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "bus__organization"
    student_path = "student"


class StudentTransportDetailView(RowLevelScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = StudentTransport.objects.select_related("student", "bus").all()
    serializer_class = StudentTransportSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "bus__organization"
    student_path = "student"


class TripListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Trip.objects.select_related("bus", "driver", "route").all()
    serializer_class = TripSerializer
    permission_classes = [IsDriverOrAdmin]
    organization_path = "bus__organization"


class TripDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Trip.objects.select_related("bus", "driver", "route").all()
    serializer_class = TripSerializer
    permission_classes = [IsDriverOrAdmin]
    organization_path = "bus__organization"


class TripStartView(OrganizationScopedMixin, generics.GenericAPIView):
    """Driver starts a trip.

    Idempotent: starting an already-running trip returns its existing start
    time rather than resetting the clock, since a flaky mobile connection can
    easily deliver the same tap twice.
    """

    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [IsDriverOrAdmin]
    organization_path = "bus__organization"

    def post(self, request, *args, **kwargs):
        trip = self.get_object()
        if trip.status != Trip.Status.IN_PROGRESS:
            trip.status = Trip.Status.IN_PROGRESS
            trip.started_at = timezone.now()
            trip.save(update_fields=["status", "started_at"])
        return Response(self.get_serializer(trip).data)


class TripEndView(OrganizationScopedMixin, generics.GenericAPIView):
    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    permission_classes = [IsDriverOrAdmin]
    organization_path = "bus__organization"

    def post(self, request, *args, **kwargs):
        trip = self.get_object()
        if trip.status != Trip.Status.COMPLETED:
            trip.status = Trip.Status.COMPLETED
            trip.ended_at = timezone.now()
            trip.save(update_fields=["status", "ended_at"])
        return Response(self.get_serializer(trip).data)


class BusLocationListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    """Drivers POST GPS pings here; admins can read the raw trail."""

    queryset = BusLocation.objects.select_related("bus").all()
    serializer_class = BusLocationSerializer
    permission_classes = [IsDriverOrAdmin]
    organization_path = "bus__organization"


class LiveTrackingView(OrganizationScopedMixin, generics.ListAPIView):
    """The newest ping per active bus.

    Answers the document's "GET /tracking - Get Live Bus Location". Readable by
    any signed-in user, since students and parents are the ones watching for
    the bus; scoping still limits them to their own college's fleet.
    """

    queryset = Bus.objects.filter(is_active=True)
    serializer_class = BusSerializer
    permission_classes = [IsAdminOrReadOnly]

    def list(self, request, *args, **kwargs):
        buses = self.get_queryset().select_related("route", "driver__user")
        payload = []
        for bus in buses:
            latest = bus.locations.first()  # model ordering is -recorded_at
            payload.append(
                {
                    "bus_id": bus.id,
                    "registration_number": bus.registration_number,
                    "route": bus.route.name if bus.route else None,
                    "driver": bus.driver.user.get_full_name() if bus.driver else None,
                    "latitude": latest.latitude if latest else None,
                    "longitude": latest.longitude if latest else None,
                    "speed_kmph": latest.speed_kmph if latest else None,
                    "recorded_at": latest.recorded_at if latest else None,
                }
            )
        return Response(payload)
