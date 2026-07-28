from django.urls import path
from .views import (
    AcademicYearListCreateView,
    AcademicYearRetrieveUpdateDestroyView,
    ClassRoomListCreateView,
    ClassRoomRetrieveUpdateDestroyView,
    SectionListCreateView,
    SectionRetrieveUpdateDestroyView,
    SubjectListCreateView,
    SubjectRetrieveUpdateDestroyView,
)

urlpatterns = [
    # Academic Year
    path(
        "academic-years/",
        AcademicYearListCreateView.as_view(),
        name="academic-year-list-create",
    ),
    path(
        "academic-years/<int:pk>/",
        AcademicYearRetrieveUpdateDestroyView.as_view(),
        name="academic-year-detail",
    ),

    # ClassRoom
    path(
        "classrooms/",
        ClassRoomListCreateView.as_view(),
        name="classroom-list-create",
    ),
    path(
        "classrooms/<int:pk>/",
        ClassRoomRetrieveUpdateDestroyView.as_view(),
        name="classroom-detail",
    ),

    # Section
    path(
        "sections/",
        SectionListCreateView.as_view(),
        name="section-list-create",
    ),
    path(
        "sections/<int:pk>/",
        SectionRetrieveUpdateDestroyView.as_view(),
        name="section-detail",
    ),

    # Subject
    path(
        "subjects/",
        SubjectListCreateView.as_view(),
        name="subject-list-create",
    ),
    path(
        "subjects/<int:pk>/",
        SubjectRetrieveUpdateDestroyView.as_view(),
        name="subject-detail",
    ),
]