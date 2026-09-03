from rest_framework import generics

from .audit import ActivityLog
from .mixins import OrganizationScopedMixin
from .permissions import IsAdmin
from .serializers import ActivityLogSerializer


class ActivityLogListView(OrganizationScopedMixin, generics.ListAPIView):
    """The document's activity log.

    Admin-only: the trail records who did what, which is itself sensitive, and
    it is also the record that would incriminate someone with access to edit it.
    Read-only by design - an audit log that can be amended proves nothing.
    """

    queryset = ActivityLog.objects.select_related("actor").all()
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()

        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        actor = self.request.query_params.get("actor")
        if actor:
            queryset = queryset.filter(actor_id=actor)

        return queryset
