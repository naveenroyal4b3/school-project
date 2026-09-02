from rest_framework import generics

from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsAdminOrReadOnly

from .models import Teacher
from .serializers import TeacherSerializer


class TeacherListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [IsAdminOrReadOnly]


class TeacherDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Teacher.objects.all()
    serializer_class = TeacherSerializer
    permission_classes = [IsAdminOrReadOnly]
