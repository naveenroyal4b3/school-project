from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = "__all__"
        read_only_fields = ["status", "sent_at", "error_message", "created_at"]


class SendNotificationSerializer(serializers.Serializer):
    """Input for the manual send endpoint (the document's POST
    /notifications/sms)."""

    recipient = serializers.IntegerField()
    title = serializers.CharField(max_length=150)
    message = serializers.CharField()
    notification_type = serializers.ChoiceField(
        choices=Notification.Type.choices,
        default=Notification.Type.GENERAL,
    )
    channel = serializers.ChoiceField(
        choices=Notification.Channel.choices,
        default=Notification.Channel.SMS,
    )
