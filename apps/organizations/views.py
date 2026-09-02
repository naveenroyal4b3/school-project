from rest_framework import viewsets

from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsSuperAdmin

from .models import Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    """Tenants themselves. Only SUPER_ADMIN may create or remove a college;
    everyone else is scoped to the single organization they belong to."""

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsSuperAdmin]
    organization_path = "id"
