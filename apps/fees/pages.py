"""Printable receipt page.

Served from the web layer rather than the API so the API keeps one content type
per endpoint. Uses Django's session login, because a printed receipt is opened
in a new tab where the front end's fetch wrapper is not running to attach
anything.
"""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from apps.accounts.models import User

from .models import FeePayment
from .receipts import receipt_context

STAFF_ROLES = (User.Role.SUPER_ADMIN, User.Role.ORGANIZATION_ADMIN, User.Role.TEACHER)


@login_required
def receipt_page(request, pk):
    payment = (
        FeePayment.objects.select_related(
            "student__user", "student__organization", "student__parent__user", "fee_structure"
        )
        .filter(pk=pk)
        .first()
    )

    user = request.user
    if payment is None:
        raise Http404

    student = payment.student

    # The same row-level rule the API applies: staff see their college, a
    # parent sees their children, a student sees themselves. A 404 rather than
    # a 403 so the endpoint does not confirm which receipts exist.
    if user.is_superuser or user.role in STAFF_ROLES:
        allowed = student.organization_id == user.organization_id or user.is_superuser
    elif user.role == User.Role.STUDENT:
        allowed = getattr(user, "student_profile", None) == student
    elif user.role == User.Role.PARENT:
        parent = getattr(user, "parent_profile", None)
        allowed = parent is not None and student.parent_id == parent.pk
    else:
        allowed = False

    if not allowed:
        raise Http404

    return render(request, "receipt.html", receipt_context(payment))
