"""Shared view mixins.

The system is multi-tenant: every record ultimately belongs to one
``Organization``. Without scoping, any authenticated user of any college could
read every other college's students, so views opt in by declaring the ORM path
from their own model to the owning organization.
"""

from apps.accounts.models import User


class OrganizationScopedMixin:
    """Restrict a view's queryset to the caller's own organization.

    ``organization_path`` is the ORM lookup from this view's model to
    ``Organization`` - ``"organization"`` when the FK is direct, or a traversal
    such as ``"classroom__academic_year__organization"``.

    SUPER_ADMIN is deliberately exempt: it administers every tenant. A user with
    no organization set sees nothing rather than everything, so a
    misconfigured account fails closed.
    """

    organization_path = "organization"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser or user.role == User.Role.SUPER_ADMIN:
            return queryset

        if user.organization_id is None:
            return queryset.none()

        return queryset.filter(**{self.organization_path: user.organization_id})
