from django.urls import path

from .views import ParentDetailView, ParentListCreateView

urlpatterns = [
    path("", ParentListCreateView.as_view(), name="parent-list"),
    path("<int:pk>/", ParentDetailView.as_view(), name="parent-detail"),
]
