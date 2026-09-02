"""QR rendering for student ID cards.

Codes are generated once and stored on StudentQRCode; the image is rendered on
demand rather than saved as a file, so there is no second copy to go stale if a
card is reissued.
"""

import io

import qrcode
from qrcode.constants import ERROR_CORRECT_Q


def render_png(payload, box_size=10, border=2):
    """Return PNG bytes for a QR encoding ``payload``.

    Error correction Q (~25% recoverable) rather than the default M: a laminated
    ID card in a school bag picks up scratches and finger grease, and the extra
    redundancy is what keeps a worn card scanning.
    """

    qr = qrcode.QRCode(
        version=None,  # let the library pick the smallest version that fits
        error_correction=ERROR_CORRECT_Q,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
