import datetime
import hashlib
import hmac
from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.testing import make_admin, make_organization, make_parent, make_student, rows
from apps.notifications.models import Notification

from .models import FeePayment, FeeStructure


class FeePaymentTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.parent = make_parent(self.org)
        self.student = make_student(self.org, parent=self.parent)
        self.admin = make_admin(self.org)

        self.fee = FeeStructure.objects.create(
            organization=self.org,
            name="Tuition",
            amount=Decimal("5000.00"),
            due_date=datetime.date(2026, 12, 31),
        )

    def test_payment_generates_a_receipt_number_and_alerts_the_guardian(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            reverse("feepayment-list"),
            {
                "student": self.student.id,
                "fee_structure": self.fee.id,
                "amount_paid": "2000.00",
                "payment_method": "UPI",
                "upi_vpa": "guardian@okhdfcbank",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["receipt_number"].startswith("RCPT-"))

        notification = Notification.objects.get()
        self.assertEqual(notification.recipient, self.parent.user)
        self.assertEqual(notification.notification_type, Notification.Type.FEE)

    def test_receipt_numbers_stay_unique_after_a_deletion(self):
        first = FeePayment.objects.create(
            student=self.student, fee_structure=self.fee, amount_paid=Decimal("100")
        )
        second = FeePayment.objects.create(
            student=self.student, fee_structure=self.fee, amount_paid=Decimal("100")
        )
        second.delete()

        third = FeePayment.objects.create(
            student=self.student, fee_structure=self.fee, amount_paid=Decimal("100")
        )
        self.assertNotEqual(first.receipt_number, third.receipt_number)

    def test_outstanding_balance_reflects_successful_payments_only(self):
        FeePayment.objects.create(
            student=self.student,
            fee_structure=self.fee,
            amount_paid=Decimal("2000.00"),
            status=FeePayment.Status.SUCCESS,
        )
        FeePayment.objects.create(
            student=self.student,
            fee_structure=self.fee,
            amount_paid=Decimal("1000.00"),
            status=FeePayment.Status.FAILED,
        )

        # 5000 charged, only the 2000 that succeeded counts.
        self.assertEqual(
            FeePayment.outstanding_for(self.student), Decimal("3000.00")
        )

    def test_zero_or_negative_payments_are_rejected(self):
        self.client.force_authenticate(self.admin)

        for amount in ["0.00", "-50.00"]:
            with self.subTest(amount=amount):
                response = self.client.post(
                    reverse("feepayment-list"),
                    {
                        "student": self.student.id,
                        "fee_structure": self.fee.id,
                        "amount_paid": amount,
                    },
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_receipt_endpoint_returns_the_printable_document(self):
        payment = FeePayment.objects.create(
            student=self.student, fee_structure=self.fee, amount_paid=Decimal("5000.00")
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(
            reverse("feepayment-receipt", args=[payment.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["receipt_number"], payment.receipt_number)
        self.assertEqual(response.data["student"]["admission_no"], self.student.admission_no)
        self.assertEqual(response.data["outstanding_balance"], Decimal("0.00"))

    def test_student_may_not_record_a_payment(self):
        self.client.force_authenticate(self.student.user)
        response = self.client.post(
            reverse("feepayment-list"),
            {
                "student": self.student.id,
                "fee_structure": self.fee.id,
                "amount_paid": "1.00",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_payments_are_scoped_to_the_callers_college(self):
        org_b = make_organization("ORGB", "School B")
        student_b = make_student(org_b, "s_b", "ADM-B", "R-B")
        fee_b = FeeStructure.objects.create(
            organization=org_b,
            name="Tuition",
            amount=Decimal("100"),
            due_date=datetime.date(2026, 12, 31),
        )
        FeePayment.objects.create(
            student=student_b, fee_structure=fee_b, amount_paid=Decimal("100")
        )

        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse("feepayment-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(rows(response)), [])


class IndianPaymentMethodTests(APITestCase):
    """Each Indian payment rail produces a different reference. A payment
    recorded without one cannot be traced to a bank statement when a parent
    disputes it, so each method must carry its own identifier."""

    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.student = make_student(self.org)
        self.admin = make_admin(self.org)
        self.fee = FeeStructure.objects.create(
            organization=self.org,
            name="Tuition",
            amount=Decimal("500000.00"),
            due_date=datetime.date(2026, 12, 31),
        )
        self.client.force_authenticate(self.admin)

    def pay(self, **extra):
        payload = {
            "student": self.student.id,
            "fee_structure": self.fee.id,
            "amount_paid": "5000.00",
        }
        payload.update(extra)
        return self.client.post(reverse("feepayment-list"), payload)

    def test_all_indian_rails_are_offered(self):
        response = self.client.get(reverse("payment-methods"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        offered = {row["value"] for row in response.data}
        self.assertEqual(
            offered,
            {
                "CASH", "UPI", "DEBIT_CARD", "CREDIT_CARD", "NET_BANKING",
                "NEFT", "RTGS", "IMPS", "WALLET", "CHEQUE", "DEMAND_DRAFT",
            },
        )

    def test_cash_needs_no_reference(self):
        self.assertEqual(self.pay(payment_method="CASH").status_code, status.HTTP_201_CREATED)

    def test_upi_accepts_a_vpa(self):
        response = self.pay(payment_method="UPI", upi_vpa="parent@okaxis")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["reference"], None)  # no txn id supplied

    def test_upi_without_a_reference_is_rejected(self):
        response = self.pay(payment_method="UPI")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("upi_vpa", response.data)

    def test_a_malformed_upi_id_is_rejected(self):
        for bad in ["parentokaxis", "@okaxis", "parent@"]:
            with self.subTest(vpa=bad):
                response = self.pay(payment_method="UPI", upi_vpa=bad)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bank_transfers_require_a_utr(self):
        for method in ["NEFT", "IMPS"]:
            with self.subTest(method=method):
                self.assertEqual(
                    self.pay(payment_method=method).status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
                self.assertEqual(
                    self.pay(
                        payment_method=method,
                        bank_reference=f"UTR{method}12345",
                        transaction_id=f"txn-{method}",
                    ).status_code,
                    status.HTTP_201_CREATED,
                )

    def test_rtgs_below_two_lakh_is_rejected(self):
        """RBI sets a Rs 2,00,000 floor on RTGS; smaller transfers go by NEFT."""
        response = self.pay(
            payment_method="RTGS", amount_paid="50000.00", bank_reference="UTR999"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("payment_method", response.data)

    def test_rtgs_at_or_above_two_lakh_is_accepted(self):
        response = self.pay(
            payment_method="RTGS", amount_paid="200000.00", bank_reference="UTR1000"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_cheque_and_dd_require_an_instrument_number(self):
        for method in ["CHEQUE", "DEMAND_DRAFT"]:
            with self.subTest(method=method):
                self.assertEqual(
                    self.pay(payment_method=method).status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
                response = self.pay(
                    payment_method=method,
                    instrument_number=f"{method}-000123",
                    bank_name="State Bank of India",
                )
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                self.assertEqual(response.data["reference"], f"{method}-000123")

    def test_cards_wallets_and_net_banking_require_a_transaction_id(self):
        for method in ["DEBIT_CARD", "CREDIT_CARD", "NET_BANKING", "WALLET"]:
            with self.subTest(method=method):
                self.assertEqual(
                    self.pay(payment_method=method).status_code,
                    status.HTTP_400_BAD_REQUEST,
                )
                self.assertEqual(
                    self.pay(
                        payment_method=method, transaction_id=f"pay_{method}"
                    ).status_code,
                    status.HTTP_201_CREATED,
                )

    def test_receipt_reports_the_rail_and_its_reference(self):
        payment = self.pay(
            payment_method="IMPS", bank_reference="UTR55512345", transaction_id="txn-imps"
        )
        response = self.client.get(
            reverse("feepayment-receipt", args=[payment.data["id"]])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payment_method"], "IMPS")


class PaymentGatewayTests(APITestCase):
    def test_console_gateway_converts_rupees_to_paise(self):
        """Indian gateways bill in the smallest unit - a rupees figure sent
        as-is would undercharge by a factor of a hundred."""
        from apps.fees.gateways import get_payment_gateway, to_minor_units

        self.assertEqual(to_minor_units(Decimal("1500.00")), 150000)
        self.assertEqual(to_minor_units(Decimal("99.99")), 9999)

        # The test runner sets DEBUG=False, which the console gateway now
        # refuses, so exercising it means saying explicitly that this is a
        # development scenario.
        with override_settings(DEBUG=True):
            order = get_payment_gateway().create_order(
                amount=Decimal("1500.00"), receipt="RCPT-00000001"
            )
        self.assertEqual(order["amount"], 150000)
        self.assertEqual(order["currency"], "INR")
        self.assertTrue(order["order_id"].startswith("order_dev_"))


class RazorpayGatewayTests(TestCase):
    """The signature is the only proof a payment happened.

    The browser reports success; only the HMAC, computed with a secret the
    browser never sees, actually establishes it.
    """

    def setUp(self):
        from apps.fees.gateways import RazorpayGateway
        with override_settings(RAZORPAY_KEY_ID="rzp_test_key",
                               RAZORPAY_KEY_SECRET="secret123"):
            self.gateway = RazorpayGateway()

    def signature_for(self, order_id, payment_id, secret="secret123"):
        return hmac.new(
            secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256
        ).hexdigest()

    def test_a_genuine_signature_verifies(self):
        good = self.signature_for("order_x", "pay_y")
        self.assertTrue(
            self.gateway.verify_payment(
                order_id="order_x", payment_id="pay_y", signature=good
            )
        )

    def test_a_forged_signature_is_rejected(self):
        forged = self.signature_for("order_x", "pay_y", secret="wrong-secret")
        self.assertFalse(
            self.gateway.verify_payment(
                order_id="order_x", payment_id="pay_y", signature=forged
            )
        )

    def test_a_signature_from_a_different_order_is_rejected(self):
        """Otherwise one valid payment could settle any number of fees."""
        other = self.signature_for("order_other", "pay_y")
        self.assertFalse(
            self.gateway.verify_payment(
                order_id="order_x", payment_id="pay_y", signature=other
            )
        )

    def test_a_missing_signature_is_rejected(self):
        self.assertFalse(
            self.gateway.verify_payment(
                order_id="order_x", payment_id="pay_y", signature=None
            )
        )

    def test_the_gateway_refuses_to_start_without_credentials(self):
        """Better a loud failure at startup than silently falling back to a
        stub that marks unpaid fees as settled."""
        from apps.fees.gateways import RazorpayGateway

        with override_settings(RAZORPAY_KEY_ID="", RAZORPAY_KEY_SECRET=""):
            with self.assertRaises(ImproperlyConfigured):
                RazorpayGateway()


class ConsoleGatewayGuardTests(TestCase):
    """The console gateway accepts every payment without taking money. Running
    it in production would mark a whole school's fees as paid."""

    def test_it_works_in_development(self):
        from apps.fees.gateways import get_payment_gateway

        with override_settings(DEBUG=True):
            self.assertEqual(get_payment_gateway().name, "console")

    def test_it_refuses_to_run_with_debug_off(self):
        from apps.fees.gateways import get_payment_gateway

        with override_settings(DEBUG=False, PAYMENT_GATEWAY=""):
            with self.assertRaises(ImproperlyConfigured):
                get_payment_gateway()

    def test_the_error_says_what_to_do_instead(self):
        from apps.fees.gateways import ConsolePaymentGateway

        with override_settings(DEBUG=False):
            with self.assertRaises(ImproperlyConfigured) as caught:
                ConsolePaymentGateway()

        self.assertIn("RazorpayGateway", str(caught.exception))
