from django.urls import path

from .views import (
    BusDetailView,
    BusListCreateView,
    BusLocationListCreateView,
    DriverDetailView,
    DriverListCreateView,
    LiveTrackingView,
    RouteDetailView,
    RouteListCreateView,
    RouteStopDetailView,
    RouteStopListCreateView,
    StudentTransportDetailView,
    StudentTransportListCreateView,
    TripDetailView,
    TripEndView,
    TripListCreateView,
    TripStartView,
)

urlpatterns = [
    path("drivers/", DriverListCreateView.as_view(), name="driver-list"),
    path("drivers/<int:pk>/", DriverDetailView.as_view(), name="driver-detail"),

    path("routes/", RouteListCreateView.as_view(), name="route-list"),
    path("routes/<int:pk>/", RouteDetailView.as_view(), name="route-detail"),

    path("stops/", RouteStopListCreateView.as_view(), name="routestop-list"),
    path("stops/<int:pk>/", RouteStopDetailView.as_view(), name="routestop-detail"),

    path("buses/", BusListCreateView.as_view(), name="bus-list"),
    path("buses/<int:pk>/", BusDetailView.as_view(), name="bus-detail"),

    path("assignments/", StudentTransportListCreateView.as_view(), name="studenttransport-list"),
    path("assignments/<int:pk>/", StudentTransportDetailView.as_view(), name="studenttransport-detail"),

    path("trips/", TripListCreateView.as_view(), name="trip-list"),
    path("trips/<int:pk>/", TripDetailView.as_view(), name="trip-detail"),
    path("trips/<int:pk>/start/", TripStartView.as_view(), name="trip-start"),
    path("trips/<int:pk>/end/", TripEndView.as_view(), name="trip-end"),

    path("locations/", BusLocationListCreateView.as_view(), name="buslocation-list"),
    path("tracking/", LiveTrackingView.as_view(), name="live-tracking"),
]
