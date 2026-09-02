from rest_framework import generics

from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsFacultyOrAdmin

from .models import AcademicYear, ClassRoom, Course, Department, Section, Subject
from .serializers import (
    AcademicYearSerializer,
    ClassRoomSerializer,
    CourseSerializer,
    DepartmentSerializer,
    SectionSerializer,
    SubjectSerializer,
)

# Faculty manage academic records per the requirements, so writes are open to
# TEACHER as well as the admin roles. Reads are open to any signed-in user -
# students and parents need timetables and subject lists.


class _AcademicView:
    permission_classes = [IsFacultyOrAdmin]


# Department
class DepartmentListCreateView(_AcademicView, OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer


class DepartmentRetrieveUpdateDestroyView(
    _AcademicView, OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView
):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer


# Course
class CourseListCreateView(_AcademicView, OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    organization_path = "department__organization"


class CourseRetrieveUpdateDestroyView(
    _AcademicView, OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView
):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    organization_path = "department__organization"


# Academic Year
class AcademicYearListCreateView(_AcademicView, OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer


class AcademicYearRetrieveUpdateDestroyView(
    _AcademicView, OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView
):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer


# ClassRoom
class ClassRoomListCreateView(_AcademicView, OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = ClassRoom.objects.all()
    serializer_class = ClassRoomSerializer
    organization_path = "academic_year__organization"


class ClassRoomRetrieveUpdateDestroyView(
    _AcademicView, OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView
):
    queryset = ClassRoom.objects.all()
    serializer_class = ClassRoomSerializer
    organization_path = "academic_year__organization"


# Section
class SectionListCreateView(_AcademicView, OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    organization_path = "classroom__academic_year__organization"


class SectionRetrieveUpdateDestroyView(
    _AcademicView, OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView
):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    organization_path = "classroom__academic_year__organization"


# Subject
class SubjectListCreateView(_AcademicView, OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    organization_path = "classroom__academic_year__organization"


class SubjectRetrieveUpdateDestroyView(
    _AcademicView, OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView
):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer
    organization_path = "classroom__academic_year__organization"
