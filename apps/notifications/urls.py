from django.urls import path

from .views import MyNotificationListView, NotificationDetailView, SendNotificationView

urlpatterns = [
    path("", MyNotificationListView.as_view(), name="notification-list"),
    path("<int:pk>/", NotificationDetailView.as_view(), name="notification-detail"),
    path("sms/", SendNotificationView.as_view(), name="notification-send"),
]
