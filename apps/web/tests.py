"""Page rendering.

The templates had no tests. A typo in a template tag, a renamed block or a
missing static file raises only when someone opens that page, and the earlier
Bootstrap pages shipped with a form that could never be submitted precisely
because nothing exercised them.

These are deliberately shallow: they assert the shell renders and carries what
the front end needs. Behaviour lives in the API, which is tested directly.
"""

from django.template.loader import get_template
from django.test import TestCase
from django.urls import reverse

from apps.common.testing import make_admin, make_organization, make_student

PAGES = [
    "page-dashboard",
    "page-login",
    "page-students",
    "page-attendance",
    "page-scanner",
    "page-id-cards",
    "page-tracking",
    "page-fees",
    "page-results",
    "page-teachers",
    "page-transport",
    "page-timetable",
    "page-notifications",
]


class PageRenderTests(TestCase):
    def test_every_page_renders(self):
        """Catches template syntax errors, which otherwise surface as a 500 in
        front of whoever opened the page."""
        for name in PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_every_template_compiles(self):
        """get_template parses without rendering, so a broken tag in a branch
        that this data happens not to reach is still caught."""
        for template in [
            "base.html", "login.html", "dashboard.html", "students.html",
            "attendance.html", "scanner.html", "id_cards.html", "tracking.html",
            "fees.html", "results.html", "receipt.html", "teachers.html",
            "transport.html", "timetable.html", "notifications.html",
        ]:
            with self.subTest(template=template):
                self.assertIsNotNone(get_template(template))

    def test_pages_set_the_csrf_cookie(self):
        """Cookie authentication rejects writes without a CSRF token, and the
        front end can only send one if the page it loaded from set it."""
        response = self.client.get(reverse("page-dashboard"))
        self.assertIn("csrftoken", response.cookies)

    def test_pages_load_the_shared_runtime(self):
        """Every page depends on app.js for the API client and toasts."""
        body = self.client.get(reverse("page-dashboard")).content.decode()
        self.assertIn("js/app.js", body)
        self.assertIn("css/app.css", body)

    def test_the_login_page_stands_alone(self):
        """It must not extend the shell, which redirects anyone without a
        session - that would be an infinite loop."""
        body = self.client.get(reverse("page-login")).content.decode()
        self.assertIn("login-form", body)
        self.assertNotIn("sidebar__nav", body)


class ReceiptPageTests(TestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.admin = make_admin(self.org)
        self.student = make_student(self.org, "s1", "ADM-1", "R-1")

    def make_payment(self):
        import datetime
        from decimal import Decimal

        from apps.fees.models import FeePayment, FeeStructure

        fee = FeeStructure.objects.create(
            organization=self.org, name="Tuition",
            amount=Decimal("1000.00"), due_date=datetime.date(2026, 12, 31),
        )
        return FeePayment.objects.create(
            student=self.student, fee_structure=fee, amount_paid=Decimal("1000.00")
        )

    def test_a_receipt_renders_for_staff(self):
        payment = self.make_payment()
        self.client.force_login(self.admin)

        response = self.client.get(reverse("page-receipt", args=[payment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, payment.receipt_number)
        self.assertContains(response, "ADM-1")

    def test_a_receipt_requires_a_session(self):
        payment = self.make_payment()
        response = self.client.get(reverse("page-receipt", args=[payment.id]))

        # Redirected to sign in rather than rendered.
        self.assertEqual(response.status_code, 302)

    def test_another_college_cannot_open_it(self):
        payment = self.make_payment()
        other = make_organization("ORGB", "School B")

        self.client.force_login(make_admin(other, "admin_b"))
        response = self.client.get(reverse("page-receipt", args=[payment.id]))

        # 404 rather than 403, so it cannot be used to discover which receipts
        # exist.
        self.assertEqual(response.status_code, 404)

    def test_a_missing_receipt_is_not_a_server_error(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("page-receipt", args=[999999]))
        self.assertEqual(response.status_code, 404)
