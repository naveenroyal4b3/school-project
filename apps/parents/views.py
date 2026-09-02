from rest_framework import generics

from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsAdminOrReadOnly

from .models import Parent
from .serializers import ParentSerializer


class ParentListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = Parent.objects.select_related("user").all()
    serializer_class = ParentSerializer
    permission_classes = [IsAdminOrReadOnly]


class ParentDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Parent.objects.select_related("user").all()
    serializer_class = ParentSerializer
    permission_classes = [IsAdminOrReadOnly]
