from rest_framework import generics, status
from rest_framework.response import Response

from apps.accounts.models import User
from apps.common.permissions import IsAdmin

from .models import Notification
from .serializers import NotificationSerializer, SendNotificationSerializer
from .services import notify


class MyNotificationListView(generics.ListAPIView):
    """A user's own inbox.

    Not organization-scoped by the shared mixin: the recipient filter is
    already narrower than the organization, and a user should never see
    another user's notifications even within the same college.
    """

    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class NotificationDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve or mark read. Restricted to the recipient for the same reason."""

    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)


class SendNotificationView(generics.GenericAPIView):
    """Admin-triggered send - the document's POST /notifications/sms."""

    serializer_class = SendNotificationSerializer
    permission_classes = [IsAdmin]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        recipients = User.objects.filter(pk=data["recipient"])
        # Admins may only message users inside their own college.
        if not request.user.is_superuser and request.user.role != User.Role.SUPER_ADMIN:
            recipients = recipients.filter(organization_id=request.user.organization_id)

        recipient = recipients.first()
        if recipient is None:
            return Response(
                {"error": "Recipient not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        notification = notify(
            recipient,
            data["title"],
            data["message"],
            notification_type=data["notification_type"],
            channel=data["channel"],
            organization=recipient.organization,
        )
        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_201_CREATED,
        )
