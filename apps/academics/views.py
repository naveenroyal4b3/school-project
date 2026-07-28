from rest_framework import generics
from .models import AcademicYear, ClassRoom, Section, Subject
from .serializers import (
    AcademicYearSerializer,
    ClassRoomSerializer,
    SectionSerializer,
    SubjectSerializer,
)


# Academic Year
class AcademicYearListCreateView(generics.ListCreateAPIView):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer


class AcademicYearRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer


# ClassRoom
class ClassRoomListCreateView(generics.ListCreateAPIView):
    queryset = ClassRoom.objects.all()
    serializer_class = ClassRoomSerializer


class ClassRoomRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ClassRoom.objects.all()
    serializer_class = ClassRoomSerializer


# Section
class SectionListCreateView(generics.ListCreateAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer


class SectionRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer


# Subject
class SubjectListCreateView(generics.ListCreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer


class SubjectRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer