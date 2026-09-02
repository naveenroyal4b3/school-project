from rest_framework import generics
from rest_framework.response import Response

from apps.common.mixins import OrganizationScopedMixin
from apps.common.permissions import IsAdmin, IsAdminOrReadOnly
from apps.notifications.models import Notification
from apps.notifications.services import notify_guardians

from .models import FeePayment, FeeStructure
from .serializers import FeePaymentSerializer, FeeStructureSerializer


class FeeStructureListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAdminOrReadOnly]


class FeeStructureDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = FeeStructure.objects.all()
    serializer_class = FeeStructureSerializer
    permission_classes = [IsAdminOrReadOnly]


class FeePaymentListCreateView(OrganizationScopedMixin, generics.ListCreateAPIView):
    queryset = FeePayment.objects.select_related("student", "fee_structure").all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"

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


class FeePaymentDetailView(OrganizationScopedMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = FeePayment.objects.select_related("student", "fee_structure").all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"


class ReceiptView(OrganizationScopedMixin, generics.RetrieveAPIView):
    """The document's "Generate Payment Receipts" - a receipt is a rendering of
    a payment, not a separate record, so there is nothing to store."""

    queryset = FeePayment.objects.select_related(
        "student__user", "student__organization", "fee_structure"
    ).all()
    serializer_class = FeePaymentSerializer
    permission_classes = [IsAdminOrReadOnly]
    organization_path = "student__organization"

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
