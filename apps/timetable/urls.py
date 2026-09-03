from django.urls import path

from .views import (
    PeriodDetailView,
    PeriodListCreateView,
    RoomDetailView,
    RoomListCreateView,
    TeacherScheduleView,
    TimetableEntryDetailView,
    TimetableEntryListCreateView,
)

urlpatterns = [
    path("", TimetableEntryListCreateView.as_view(), name="timetable-list"),
    path("<int:pk>/", TimetableEntryDetailView.as_view(), name="timetable-detail"),

    path("rooms/", RoomListCreateView.as_view(), name="room-list"),
    path("rooms/<int:pk>/", RoomDetailView.as_view(), name="room-detail"),

    path("periods/", PeriodListCreateView.as_view(), name="period-list"),
    path("periods/<int:pk>/", PeriodDetailView.as_view(), name="period-detail"),

    path("teachers/<int:teacher_id>/", TeacherScheduleView.as_view(), name="teacher-schedule"),
]
