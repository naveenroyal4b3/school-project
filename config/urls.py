from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    path("api/accounts/", include("apps.accounts.urls")),   # 👈 ADD THIS
    path("api/", include("apps.organizations.urls")),
    path("api/academics/", include("apps.academics.urls")),
    path("api/teachers/", include("apps.teachers.urls")),
    path("api/students/", include("apps.students.urls")),
    path("api/parents/", include("apps.parents.urls")),
    path("api/transport/", include("apps.transport.urls")),
    path("api/attendance/", include("apps.attendance.urls")),
    path("api/fees/", include("apps.fees.urls")),
    path("api/examinations/", include("apps.examinations.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/", include("apps.dashboard.urls")),
]
