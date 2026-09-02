import datetime
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.testing import make_admin, make_organization, make_parent, make_student
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
        self.assertEqual(list(response.data), [])
