"""Server-rendered shell for the front end.

The pages are thin: each template loads and then talks to the REST API over
fetch with the JWT it holds, which is the split the project document's
architecture diagram shows (Django frontend -> REST APIs -> Django backend).
Access control therefore stays in one place - the API - rather than being
duplicated in template logic where a second copy would drift.
"""

from django.views.generic import TemplateView


class Page(TemplateView):
    """Base for every page. Kept so a future shared context - feature flags,
    build version - lands in one place."""


class LoginPageView(Page):
    template_name = "login.html"


class DashboardPageView(Page):
    template_name = "dashboard.html"


class StudentsPageView(Page):
    template_name = "students.html"


class AttendancePageView(Page):
    template_name = "attendance.html"


class ScannerPageView(Page):
    template_name = "scanner.html"


class IDCardPageView(Page):
    template_name = "id_cards.html"


class TrackingPageView(Page):
    template_name = "tracking.html"


class FeesPageView(Page):
    template_name = "fees.html"


class ResultsPageView(Page):
    template_name = "results.html"
