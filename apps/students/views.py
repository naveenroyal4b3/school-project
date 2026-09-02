from rest_framework import generics

from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsAdminOrReadOnly

from .models import Student
from .serializers import StudentSerializer


class StudentListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAdminOrReadOnly]


class StudentDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAdminOrReadOnly]
