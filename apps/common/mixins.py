"""Shared view mixins.

Two layers of narrowing sit between a request and the rows it can reach:

1. Organization scoping - which tenant's data this user belongs to.
2. Row-level scoping - which records *within* that tenant they may see.

The second matters as much as the first. Roles alone answer "what may this
person do", not "whose records may they touch", so without it any signed-in
student could read every classmate's date of birth and home address.
"""

from django.db.models import Q

from apps.accounts.models import User

STAFF_ROLES = (User.Role.SUPER_ADMIN, User.Role.ORGANIZATION_ADMIN, User.Role.TEACHER)


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


class RowLevelScopedMixin(OrganizationScopedMixin):
    """Narrow a tenant's rows to the ones this person is entitled to.

    Staff (admins and faculty) see their whole college, which is what running
    one requires. Everyone else sees only records about themselves or the
    students in their care:

    * STUDENT - their own records.
    * PARENT  - their children's records.
    * DRIVER  - the students assigned to the bus they drive, needed to work a
      trip list; a driver has no business reading the rest of the school.

    ``student_path`` is the ORM lookup from this view's model to ``Student``.
    Leave it None when the view's model *is* Student.

    A role this mixin does not recognise sees nothing. New roles must be
    granted access deliberately rather than inheriting it by omission.
    """

    student_path = None

    def _lookup(self, suffix=""):
        """Build a filter key from the view's model towards Student."""
        if self.student_path is None:
            return suffix.lstrip("_") or "pk"
        return f"{self.student_path}__{suffix}".rstrip("_") if suffix else self.student_path

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser or user.role in STAFF_ROLES:
            return queryset

        if user.role == User.Role.STUDENT:
            student = getattr(user, "student_profile", None)
            if student is None:
                return queryset.none()
            if self.student_path is None:
                return queryset.filter(pk=student.pk)
            return queryset.filter(**{self.student_path: student.pk})

        if user.role == User.Role.PARENT:
            parent = getattr(user, "parent_profile", None)
            if parent is None:
                return queryset.none()
            return queryset.filter(**{self._lookup("parent"): parent.pk})

        if user.role == User.Role.DRIVER:
            driver = getattr(user, "driver_profile", None)
            if driver is None:
                return queryset.none()
            return queryset.filter(
                **{self._lookup("transport__bus__driver"): driver.pk}
            )

        return queryset.none()


class SelfOrStaffQuerysetMixin(RowLevelScopedMixin):
    """Row-level scoping for models reached through more than one path.

    Notifications, for instance, belong to a recipient rather than a student.
    Subclasses override ``personal_filter`` to say what "mine" means.
    """

    def personal_filter(self, user):
        return Q(pk__in=[])

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role in STAFF_ROLES:
            return OrganizationScopedMixin.get_queryset(self)
        return OrganizationScopedMixin.get_queryset(self).filter(self.personal_filter(user))
