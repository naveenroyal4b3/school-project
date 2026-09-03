from rest_framework import generics

from apps.common.archive import ArchiveOnDeleteMixin
from apps.common.audit import AuditedMixin
from apps.common.mixins import RowLevelScopedMixin
from apps.common.permissions import IsAdminOrReadOnly

from .models import Student
from .serializers import StudentSerializer


class StudentQuerysetMixin(RowLevelScopedMixin):
    """Shared base queryset.

    Row-level scoped: staff see the college, a student sees only their own
    record, and a parent only their children. select_related covers the joins
    the serializer always reads - without it a page of 25 students issues 100
    extra queries for names, classes and guardians.
    """

    queryset = Student.objects.select_related(
        "user", "classroom", "parent__user", "organization"
    ).all()
    serializer_class = StudentSerializer
    permission_classes = [IsAdminOrReadOnly]


class StudentListCreateView(AuditedMixin, StudentQuerysetMixin, generics.ListCreateAPIView):
    def get_queryset(self):
        queryset = super().get_queryset()

        # One search box across the identifiers and names staff actually
        # remember, rather than a separate filter per column.
        term = self.request.query_params.get("search")
        if term:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(admission_no__icontains=term)
                | Q(roll_number__icontains=term)
                | Q(user__first_name__icontains=term)
                | Q(user__last_name__icontains=term)
                | Q(user__username__icontains=term)
            )

        # Archived students are hidden by the default manager; this exposes
        # them deliberately, for a leavers report or to restore one.
        if self.request.query_params.get("archived") == "true":
            queryset = Student.all_objects.filter(archived_at__isnull=False)
            user = self.request.user
            if not user.is_superuser and user.organization_id:
                queryset = queryset.filter(organization_id=user.organization_id)

        is_active = self.request.query_params.get("is_active")
        if is_active in ("true", "false"):
            queryset = queryset.filter(is_active=is_active == "true")

        for field in ("classroom", "section", "academic_year", "parent"):
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{f"{field}_id": value})

        return queryset.order_by("admission_no")


class StudentDetailView(
    # AuditedMixin first: it records the removal and then delegates to
    # ArchiveOnDeleteMixin. Reversed, the archiver ends the chain and the
    # deletion never reaches the audit trail.
    AuditedMixin, ArchiveOnDeleteMixin, StudentQuerysetMixin,
    generics.RetrieveUpdateDestroyAPIView,
):
    pass
