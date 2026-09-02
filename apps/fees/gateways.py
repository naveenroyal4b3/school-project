"""Online payment gateway integration.

The project document names a "Payment Gateway API" without choosing a provider,
so this sits behind the same kind of swappable backend as the SMS sender. The
default records the intent and settles nothing, which keeps development and the
test suite off a live payment network.

An Indian deployment would point ``PAYMENT_GATEWAY`` at a Razorpay, PayU or
Cashfree implementation of the same two methods. Note that gateways return
amounts in paise, not rupees - hence ``to_minor_units``.
"""

import logging
import uuid
from decimal import Decimal

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)


def to_minor_units(amount):
    """Rupees to paise. Indian gateways bill in the smallest unit."""
    return int((Decimal(amount) * 100).to_integral_value())


class ConsolePaymentGateway:
    """Development gateway. Issues an order id and accepts every verification.

    Never enable this in production: it would mark unpaid fees as settled.
    """

    name = "console"

    def create_order(self, *, amount, receipt, currency="INR"):
        order_id = f"order_dev_{uuid.uuid4().hex[:14]}"
        logger.info(
            "gateway(console): order %s for %s %s (receipt %s)",
            order_id,
            currency,
            amount,
            receipt,
        )
        return {
            "gateway": self.name,
            "order_id": order_id,
            "amount": to_minor_units(amount),
            "currency": currency,
            "receipt": receipt,
        }

    def verify_payment(self, *, order_id, payment_id, signature=None):
        logger.info("gateway(console): accepting payment %s for order %s", payment_id, order_id)
        return True


def get_payment_gateway():
    path = getattr(settings, "PAYMENT_GATEWAY", "")
    if not path:
        return ConsolePaymentGateway()
    return import_string(path)()
