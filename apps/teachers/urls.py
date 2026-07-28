from django.urls import path
from .views import TeacherListCreateView, TeacherDetailView

urlpatterns = [
    path("", TeacherListCreateView.as_view(), name="teacher-list"),
    path("<int:pk>/", TeacherDetailView.as_view(), name="teacher-detail"),
]