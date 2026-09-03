from rest_framework import generics
from rest_framework.response import Response

from apps.common.audit import AuditedMixin
from apps.common.mixins import OrganizationScopedMixin, RowLevelScopedMixin
from apps.common.permissions import IsAdmin, IsAdminOrReadOnly
from apps.notifications.models import Notification
from apps.notifications.services import notify_guardians

from .models import RTGS_MINIMUM, FeePayment, FeeStructure
from .receipts import receipt_context
from .serializers import (
    FeePaymentSerializer,
    FeeStructureSerializer,
    PaymentMethodSerializer,
)


class FeeStructureListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAdminOrReadOnly]


class FeeStructureDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAdminOrReadOnly]


class FeePaymentListCreateView(AuditedMixin, RowLevelScopedMixin, generics.ListCreateAPIView):
    queryset = FeePayment.objects.select_related("student", "fee_structure").all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"
    student_path = "student"

    def get_queryset(self):
        queryset = super().get_queryset()
        student = self.request.query_params.get("student")
        if student:
            queryset = queryset.filter(student_id=student)
        return queryset

    def perform_create(self, serializer):
        payment = serializer.save()
        if payment.status == FeePayment.Status.SUCCESS:
            notify_guardians(
                payment.student,
                title="Fee payment received",
                message=(
                    f"Payment of {payment.amount_paid} received for "
                    f"{payment.fee_structure.name}. Receipt {payment.receipt_number}."
                ),
                notification_type=Notification.Type.FEE,
            )


class FeePaymentDetailView(AuditedMixin, RowLevelScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = FeePayment.objects.select_related("student", "fee_structure").all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"
    student_path = "student"


class ReceiptView(RowLevelScopedMixin, generics.RetrieveAPIView):
    """The document's "Generate Payment Receipts".

    A receipt is a rendering of a payment, not a separate record, so there is
    nothing to store. Returns a printable page by default and JSON when asked,
    because a parent wants something to keep while the front end wants data.

    Row-level scoped, so a parent can open their own child's receipt and nobody
    else's.
    """

    queryset = FeePayment.objects.select_related(
        "student__user", "student__organization", "fee_structure"
    ).all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"
    student_path = "student"

    def retrieve(self, request, *args, **kwargs):
        payment = self.get_object()
        student = payment.student

        return Response(
            {
                "receipt_number": payment.receipt_number,
                "issued_on": payment.payment_date,
                "organization": student.organization.organization_name
                if student.organization
                else None,
                "student": {
                    "name": student.user.get_full_name() or student.user.username,
                    "admission_no": student.admission_no,
                    "roll_number": student.roll_number,
                },
                "fee": {
                    "name": payment.fee_structure.name,
                    "amount_due": payment.fee_structure.amount,
                },
                "amount_paid": payment.amount_paid,
                "payment_method": payment.payment_method,
                "transaction_id": payment.transaction_id,
                "status": payment.status,
                "outstanding_balance": FeePayment.outstanding_for(student),
            }
        )


class StudentFeeSummaryView(generics.GenericAPIView):
    """Everything owed and paid for one student."""

    permission_classes = [IsAdmin]
    serializer_class = FeePaymentSerializer

    def get(self, request, student_id, *args, **kwargs):
        from apps.students.models import Student

        students = Student.objects.all()
        if not request.user.is_superuser and request.user.organization_id is not None:
            students = students.filter(organization_id=request.user.organization_id)

        student = students.filter(pk=student_id).first()
        if student is None:
            return Response({"error": "Student not found."}, status=404)

        payments = student.fee_payments.select_related("fee_structure").all()
        return Response(
            {
                "student": student.admission_no,
                "outstanding_balance": FeePayment.outstanding_for(student),
                "payments": FeePaymentSerializer(payments, many=True).data,
            }
        )


# Grouping and the reference each rail needs, served to the front end so the
# payment form does not carry a second copy of the rules that live in the
# serializer.
METHOD_METADATA = {
    FeePayment.Method.CASH: ("Cash & instruments", None, None),
    FeePayment.Method.CHEQUE: ("Cash & instruments", "instrument_number", None),
    FeePayment.Method.DEMAND_DRAFT: ("Cash & instruments", "instrument_number", None),
    FeePayment.Method.UPI: ("UPI", "upi_vpa", None),
    FeePayment.Method.DEBIT_CARD: ("Cards", "transaction_id", None),
    FeePayment.Method.CREDIT_CARD: ("Cards", "transaction_id", None),
    FeePayment.Method.NET_BANKING: ("Online", "transaction_id", None),
    FeePayment.Method.WALLET: ("Online", "transaction_id", None),
    FeePayment.Method.NEFT: ("Bank transfer", "bank_reference", None),
    FeePayment.Method.IMPS: ("Bank transfer", "bank_reference", None),
    FeePayment.Method.RTGS: ("Bank transfer", "bank_reference", RTGS_MINIMUM),
}


class PaymentMethodListView(generics.ListAPIView):
    """GET /api/fees/methods/ - the supported payment rails."""

    serializer_class = PaymentMethodSerializer
    pagination_class = None

    def get_queryset(self):
        return [
            {
                "value": value,
                "label": label,
                "group": METHOD_METADATA[value][0],
                "requires": METHOD_METADATA[value][1],
                "minimum": METHOD_METADATA[value][2],
            }
            for value, label in FeePayment.Method.choices
        ]

    def list(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)
