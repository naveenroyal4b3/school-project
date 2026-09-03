from django.urls import path

from .views import ActivityLogListView

urlpatterns = [
    path("activity/", ActivityLogListView.as_view(), name="activity-log"),
]
