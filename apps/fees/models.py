"""Fee & Payment Management.

Covers the document's Fees & Payments tables and its "Generate Payment
Receipts" feature. One Student -> Many Fee Payments.
"""

from decimal import Decimal

from django.db import models
from django.db.models import Sum

from apps.academics.models import AcademicYear, ClassRoom, Course
from apps.organizations.models import Organization
from apps.students.models import Student

# RBI sets a floor of Rs 2,00,000 on RTGS transfers; anything smaller has to go
# by NEFT or IMPS. Enforced in the serializer so a payment is not recorded
# against a rail that could not have carried it.
RTGS_MINIMUM = Decimal("200000.00")


class FeeStructure(models.Model):
    """A charge that applies to a group of students.

    Scoped by classroom or course rather than assigned per student, so adding a
    new student to a class automatically makes them liable for that class's
    fees instead of needing a manual copy of every charge.
    """

    class Frequency(models.TextChoices):
        ONE_TIME = "ONE_TIME", "One Time"
        MONTHLY = "MONTHLY", "Monthly"
        QUARTERLY = "QUARTERLY", "Quarterly"
        ANNUAL = "ANNUAL", "Annual"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="fee_structures",
    )

    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name="fee_structures",
        null=True,
        blank=True,
    )

    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name="fee_structures",
        null=True,
        blank=True,
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="fee_structures",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=100)

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    frequency = models.CharField(
        max_length=10,
        choices=Frequency.choices,
        default=Frequency.ONE_TIME,
    )

    due_date = models.DateField()

    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.amount})"


class FeePayment(models.Model):
    """One payment against one fee structure.

    Partial payments are allowed - several rows may point at the same
    structure - so the outstanding balance is always derived by summing
    payments rather than stored as a mutable field that could drift.
    """

    class Method(models.TextChoices):
        """Payment rails in common use in India.

        Grouped as: cash and paper instruments, cards, and the electronic rails
        (UPI, net banking, the NEFT/RTGS/IMPS bank transfers, and wallets).
        Each carries a different reference number, which is why the reference
        fields below are separate rather than one overloaded column.
        """

        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"
        DEBIT_CARD = "DEBIT_CARD", "Debit Card"
        CREDIT_CARD = "CREDIT_CARD", "Credit Card"
        NET_BANKING = "NET_BANKING", "Net Banking"
        NEFT = "NEFT", "NEFT"
        RTGS = "RTGS", "RTGS"
        IMPS = "IMPS", "IMPS"
        WALLET = "WALLET", "Wallet"
        CHEQUE = "CHEQUE", "Cheque"
        DEMAND_DRAFT = "DEMAND_DRAFT", "Demand Draft"

    # Rails that settle through a bank and carry a UTR.
    BANK_TRANSFER_METHODS = ("NEFT", "RTGS", "IMPS")
    # Rails represented by a physical instrument with a printed number.
    INSTRUMENT_METHODS = ("CHEQUE", "DEMAND_DRAFT")
    CARD_METHODS = ("DEBIT_CARD", "CREDIT_CARD")

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="fee_payments",
    )

    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)

    payment_method = models.CharField(
        max_length=15,
        choices=Method.choices,
        default=Method.CASH,
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.SUCCESS,
    )

    # From the payment gateway, when one was used. Unique but nullable: cash
    # payments have no transaction id, and two blank strings would collide.
    transaction_id = models.CharField(
        max_length=100, unique=True, null=True, blank=True
    )

    # UPI virtual payment address the money came from, e.g. name@okhdfcbank.
    upi_vpa = models.CharField(max_length=100, blank=True, null=True)

    # UTR / bank reference for NEFT, RTGS and IMPS transfers.
    bank_reference = models.CharField(max_length=50, blank=True, null=True)

    # Cheque or demand draft number.
    instrument_number = models.CharField(max_length=30, blank=True, null=True)

    instrument_date = models.DateField(blank=True, null=True)

    bank_name = models.CharField(max_length=100, blank=True, null=True)

    # Which gateway processed an online payment, when one did.
    gateway = models.CharField(max_length=30, blank=True, null=True)

    gateway_order_id = models.CharField(max_length=100, blank=True, null=True)

    receipt_number = models.CharField(max_length=30, unique=True, editable=False)

    payment_date = models.DateField(auto_now_add=True)

    remarks = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["student", "-created_at"])]

    @property
    def reference(self):
        """The reference a parent would quote, whichever rail was used."""
        return (
            self.transaction_id
            or self.bank_reference
            or self.instrument_number
            or None
        )

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            # Derived from the primary key sequence rather than a count, which
            # would repeat a number after any deletion.
            last = FeePayment.objects.order_by("-id").values_list("id", flat=True).first() or 0
            self.receipt_number = f"RCPT-{last + 1:08d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} {self.student.admission_no} {self.amount_paid}"

    @staticmethod
    def outstanding_for(student):
        """Total still owed by a student across every fee that applies to them."""
        applicable = FeeStructure.objects.filter(
            organization=student.organization, is_active=True
        ).filter(
            models.Q(classroom__isnull=True) | models.Q(classroom=student.classroom)
        )

        charged = applicable.aggregate(total=Sum("amount"))["total"] or Decimal("0")
        paid = student.fee_payments.filter(
            status=FeePayment.Status.SUCCESS
        ).aggregate(total=Sum("amount_paid"))["total"] or Decimal("0")

        return charged - paid
