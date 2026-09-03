"""Online payment gateway integration.

The project document names a "Payment Gateway API" without choosing a provider,
so this sits behind the same kind of swappable backend as the SMS sender. The
default records the intent and settles nothing, which keeps development and the
test suite off a live payment network.

An Indian deployment would point ``PAYMENT_GATEWAY`` at a Razorpay, PayU or
Cashfree implementation of the same two methods. Note that gateways return
amounts in paise, not rupees - hence ``to_minor_units``.
"""

import base64
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.request
import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string


class PaymentGatewayError(Exception):
    """Raised when a gateway cannot be reached or refuses a request.

    Distinct from a declined payment: this means we do not know the outcome,
    and an unknown outcome must never be recorded as paid.
    """


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


class RazorpayGateway:
    """Razorpay, the most widely used gateway for Indian school fee collection.

    Kept dependency-free: the REST API is two HTTPS calls, so importing the SDK
    would add a package for no benefit. Credentials come from the environment -
    a key committed to the repository is a key that has to be rotated.

    Signature verification is done here rather than trusted from the client.
    The browser reports "payment succeeded"; only the HMAC, computed with the
    secret the browser never sees, proves it.
    """

    name = "razorpay"
    API_ROOT = "https://api.razorpay.com/v1"

    def __init__(self):
        self.key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
        self.key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")
        if not (self.key_id and self.key_secret):
            raise ImproperlyConfigured(
                "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set to use "
                "the Razorpay gateway."
            )

    def create_order(self, *, amount, receipt, currency="INR"):
        payload = json.dumps({
            "amount": to_minor_units(amount),   # paise, not rupees
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1,
        }).encode()

        request = urllib.request.Request(
            f"{self.API_ROOT}/orders",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Basic " + base64.b64encode(
                    f"{self.key_id}:{self.key_secret}".encode()
                ).decode(),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                order = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            raise PaymentGatewayError(f"Razorpay rejected the order: {detail}") from exc
        except urllib.error.URLError as exc:
            # A timeout here means no order exists, so the fee is simply not
            # collected - never record it as paid.
            raise PaymentGatewayError(f"Could not reach Razorpay: {exc.reason}") from exc

        return {
            "gateway": self.name,
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "receipt": receipt,
            "key_id": self.key_id,   # public; the checkout widget needs it
        }

    def verify_payment(self, *, order_id, payment_id, signature=None):
        """Confirm the callback really came from Razorpay."""
        if not signature:
            return False

        expected = hmac.new(
            self.key_secret.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()

        # Constant-time: a plain == leaks how much of the signature matched.
        return hmac.compare_digest(expected, signature)
