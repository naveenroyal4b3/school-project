from rest_framework import serializers

from .models import RTGS_MINIMUM, FeePayment, FeeStructure


class FeeStructureSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = "__all__"


class FeePaymentSerializer(serializers.ModelSerializer):
    admission_no = serializers.CharField(source="student.admission_no", read_only=True)
    fee_name = serializers.CharField(source="fee_structure.name", read_only=True)
    method_label = serializers.CharField(source="get_payment_method_display", read_only=True)
    reference = serializers.CharField(read_only=True)

    class Meta:
        model = FeePayment
        fields = "__all__"
        read_only_fields = ["receipt_number", "payment_date", "created_at"]

    def validate_amount_paid(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate_upi_vpa(self, value):
        # A VPA is always handle@bank. Catching a malformed one here beats
        # discovering it when a parent disputes a payment months later.
        if value and ("@" not in value or value.startswith("@") or value.endswith("@")):
            raise serializers.ValidationError(
                "Enter a valid UPI ID, for example name@okhdfcbank."
            )
        return value

    def validate(self, attrs):
        """Require the reference that each rail actually produces.

        A payment recorded with no way to trace it back to a bank statement is
        worthless when a parent disputes it, so each method must carry its own
        identifier.
        """

        def value(field):
            if field in attrs:
                return attrs[field]
            return getattr(self.instance, field, None)

        method = value("payment_method")
        amount = value("amount_paid")
        errors = {}

        if method == FeePayment.Method.UPI:
            if not value("upi_vpa") and not value("transaction_id"):
                errors["upi_vpa"] = "Record the payer's UPI ID or the transaction reference."

        elif method in FeePayment.BANK_TRANSFER_METHODS:
            if not value("bank_reference"):
                errors["bank_reference"] = f"{method} transfers need the UTR reference number."

            if method == FeePayment.Method.RTGS and amount and amount < RTGS_MINIMUM:
                errors["payment_method"] = (
                    f"RTGS has a minimum of {RTGS_MINIMUM:,.0f}. "
                    "Use NEFT or IMPS for smaller amounts."
                )

        elif method in FeePayment.INSTRUMENT_METHODS:
            if not value("instrument_number"):
                label = "Cheque" if method == FeePayment.Method.CHEQUE else "Demand draft"
                errors["instrument_number"] = f"{label} payments need the instrument number."

        elif method in FeePayment.CARD_METHODS or method in (
            FeePayment.Method.NET_BANKING,
            FeePayment.Method.WALLET,
        ):
            if not value("transaction_id"):
                errors["transaction_id"] = "Online payments need the gateway transaction reference."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


class PaymentMethodSerializer(serializers.Serializer):
    """Describes the rails to the front end, so the payment form can show the
    right reference field without duplicating the rules in JavaScript."""

    value = serializers.CharField()
    label = serializers.CharField()
    group = serializers.CharField()
    requires = serializers.CharField(allow_null=True)
    minimum = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True
    )
