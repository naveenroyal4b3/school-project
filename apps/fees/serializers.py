from rest_framework import serializers

from .models import FeePayment, FeeStructure


class FeeStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = "__all__"


class FeePaymentSerializer(serializers.ModelSerializer):
    admission_no = serializers.CharField(source="student.admission_no", read_only=True)
    fee_name = serializers.CharField(source="fee_structure.name", read_only=True)

    class Meta:
        model = FeePayment
        fields = "__all__"
        read_only_fields = ["receipt_number", "payment_date", "created_at"]

    def validate_amount_paid(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value
