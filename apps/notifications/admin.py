from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "notification_type", "channel", "status", "created_at")
    list_filter = ("notification_type", "channel", "status")
    search_fields = ("title", "message", "recipient__username")
