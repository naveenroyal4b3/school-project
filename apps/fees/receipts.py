"""Printable fee receipts.

The project document asks for generated receipts. A parent needs something they
can keep, and a school needs something it can hand over the counter, so the
receipt is rendered as a page the browser prints rather than a JSON blob.

Deliberately HTML with a print stylesheet rather than a PDF library: it adds no
dependency, it prints to PDF from any browser, and it stays legible on the
phone a parent opens it on. A server-generated PDF would need ReportLab or
WeasyPrint, and WeasyPrint needs system libraries that make the Docker image
considerably larger.
"""

from decimal import Decimal

from django.utils import timezone


def receipt_context(payment):
    """Everything the receipt template renders.

    Assembled here rather than in the template so the same figures can serve a
    future emailed copy without the arithmetic being written twice.
    """
    student = payment.student
    organization = student.organization
    fee = payment.fee_structure

    charged = fee.amount or Decimal("0")
    paid = payment.amount_paid or Decimal("0")

    from .models import FeePayment

    return {
        "payment": payment,
        "student": student,
        "organization": organization,
        "fee": fee,
        "student_name": student.user.get_full_name() or student.user.username,
        "reference": payment.reference,
        "method_label": payment.get_payment_method_display(),
        # This receipt's own balance, not the student's overall position: a
        # part payment must show what is still owed on the charge it covers.
        "balance_on_this_fee": charged - paid,
        "outstanding_total": FeePayment.outstanding_for(student),
        "issued_at": timezone.localtime(),
        "is_settled": paid >= charged,
    }
