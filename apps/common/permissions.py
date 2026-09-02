"""Role-based permission classes.

Implements the "Role-Based Access" functional requirement. The five actors
named in the project document map onto ``User.Role`` as follows::

    Admin   -> SUPER_ADMIN, ORGANIZATION_ADMIN
    Faculty -> TEACHER
    Student -> STUDENT
    Parent  -> PARENT
    Driver  -> DRIVER

Every class here assumes ``IsAuthenticated`` has already run (it is the
project-wide default in settings.REST_FRAMEWORK), so ``request.user`` is
always a real user by the time these are consulted.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.models import User

ADMIN_ROLES = (User.Role.SUPER_ADMIN, User.Role.ORGANIZATION_ADMIN)


class RolePermission(BasePermission):
    """Grant access by role, separately for reads and writes.

    Subclasses set ``read_roles`` and ``write_roles``. An empty tuple means
    "no role qualifies"; use ``ANY`` to admit every authenticated user.
    """

    ANY = "__any__"

    read_roles: tuple = ()
    write_roles: tuple = ()

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False

        # A Django superuser bypasses role checks so the project always has a
        # way back in through the admin site.
        if user.is_superuser:
            return True

        allowed = self.read_roles if request.method in SAFE_METHODS else self.write_roles
        if self.ANY in allowed:
            return True
        return user.role in allowed


class IsSuperAdmin(RolePermission):
    read_roles = (User.Role.SUPER_ADMIN,)
    write_roles = (User.Role.SUPER_ADMIN,)


class IsAdmin(RolePermission):
    """Admin actors only - manages campus operations end to end."""

    read_roles = ADMIN_ROLES
    write_roles = ADMIN_ROLES


class IsAdminOrReadOnly(RolePermission):
    """Anyone signed in may read; only admins may change."""

    read_roles = (RolePermission.ANY,)
    write_roles = ADMIN_ROLES


class IsFacultyOrAdmin(RolePermission):
    """Faculty manage attendance, examinations and academic records."""

    read_roles = (RolePermission.ANY,)
    write_roles = ADMIN_ROLES + (User.Role.TEACHER,)


class IsDriverOrAdmin(RolePermission):
    """Drivers update trips and push live bus locations."""

    read_roles = (RolePermission.ANY,)
    write_roles = ADMIN_ROLES + (User.Role.DRIVER,)
