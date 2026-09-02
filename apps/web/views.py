"""Server-rendered shell for the front end.

The pages are thin: each template loads and then talks to the REST API over
AJAX with the JWT it holds, which is the split the project document's
architecture diagram shows (Django frontend -> REST APIs -> Django backend).
Access control therefore stays in one place - the API - rather than being
duplicated in template logic.
"""

from django.views.generic import TemplateView


class LoginPageView(TemplateView):
    template_name = "login.html"


class DashboardPageView(TemplateView):
    template_name = "dashboard.html"


class StudentsPageView(TemplateView):
    template_name = "students.html"


class AttendancePageView(TemplateView):
    template_name = "attendance.html"


class TrackingPageView(TemplateView):
    template_name = "tracking.html"


class FeesPageView(TemplateView):
    template_name = "fees.html"
