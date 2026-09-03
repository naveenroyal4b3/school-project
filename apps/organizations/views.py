from rest_framework import generics, viewsets
from rest_framework.exceptions import NotFound

from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsAdmin, IsSuperAdmin

from .models import Organization
from .serializers import OrganizationBrandingSerializer, OrganizationSerializer


class OrganizationViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    """Tenants themselves.

    Only SUPER_ADMIN may create a college or remove one - that is platform
    administration. An ORGANIZATION_ADMIN may read and update the single
    organization they belong to, which is what makes the branding settings
    usable: a client changing their own logo and colours should not need the
    platform owner to do it for them.
    """

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    organization_path = "id"

    def get_permissions(self):
        if self.action in ("list", "retrieve", "update", "partial_update"):
            return [IsAdmin()]
        return [IsSuperAdmin()]


class MyOrganizationView(generics.RetrieveAPIView):
    """GET /api/organizations/me/ - branding for the caller's own tenant.

    Readable by every signed-in role, unlike the admin-only organization
    endpoints: the front end cannot render its header, colours or labels
    without it, and a student loading the app needs the same branding an
    administrator does.
    """

    serializer_class = OrganizationBrandingSerializer

    def get_object(self):
        organization = self.request.user.organization
        if organization is None:
            raise NotFound("Your account is not linked to an organization.")
        return organization
