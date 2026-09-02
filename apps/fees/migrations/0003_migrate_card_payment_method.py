"""Map the retired CARD method onto DEBIT_CARD.

The Method choices were split into DEBIT_CARD and CREDIT_CARD so each carries
its own reference. Django does not enforce choices at the database level, so
existing CARD rows would survive silently and then fail validation the next
time anyone edited them. DEBIT_CARD is the safe destination: it is by far the
more common of the two in Indian school fee collection, and the split is
recorded in remarks so the original value is not lost.
"""

from django.db import migrations


def card_to_debit_card(apps, schema_editor):
    FeePayment = apps.get_model("fees", "FeePayment")

    for payment in FeePayment.objects.filter(payment_method="CARD"):
        payment.payment_method = "DEBIT_CARD"
        note = "Migrated from legacy CARD method"
        payment.remarks = f"{payment.remarks}. {note}" if payment.remarks else note
        payment.save(update_fields=["payment_method", "remarks"])


def debit_card_to_card(apps, schema_editor):
    """Reverse. Only rows this migration touched are moved back, identified by
    the note it left, so genuinely new DEBIT_CARD payments are not rewritten."""

    FeePayment = apps.get_model("fees", "FeePayment")

    for payment in FeePayment.objects.filter(
        payment_method="DEBIT_CARD",
        remarks__contains="Migrated from legacy CARD method",
    ):
        payment.payment_method = "CARD"
        payment.save(update_fields=["payment_method"])


class Migration(migrations.Migration):

    dependencies = [
        ("fees", "0002_feepayment_bank_name_feepayment_bank_reference_and_more"),
    ]

    operations = [
        migrations.RunPython(card_to_debit_card, debit_card_to_card),
    ]
