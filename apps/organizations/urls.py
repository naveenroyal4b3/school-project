from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MyOrganizationView, OrganizationViewSet

router = DefaultRouter()
router.register("organizations", OrganizationViewSet)

urlpatterns = [
    # Declared before the router so "me" is not captured as a primary key.
    path("organizations/me/", MyOrganizationView.as_view(), name="my-organization"),
    path("", include(router.urls)),
]