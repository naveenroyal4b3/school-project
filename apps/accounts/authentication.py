"""Cookie-based JWT authentication.

Tokens used to live in ``localStorage``, where any successful XSS reads them and
becomes a full account takeover. Moving them into httpOnly cookies makes that
structurally impossible rather than dependent on every template escaping
correctly.

Cookies are sent automatically by the browser, which reintroduces CSRF - so
unlike header authentication, this class must enforce a CSRF token on unsafe
methods, exactly as ``SessionAuthentication`` does.

The ``Authorization: Bearer`` header still works. Mobile apps and server-to-
server callers have no cookie jar, and they are not vulnerable to CSRF because
nothing attaches the header for them.
"""

from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

ACCESS_COOKIE = "sms_access"
REFRESH_COOKIE = "sms_refresh"


class _CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        return reason


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # A header, when present, wins: an explicit credential should not be
        # silently overridden by whatever cookie the browser happened to send.
        header_result = super().authenticate(request)
        if header_result is not None:
            return header_result

        raw_token = request.COOKIES.get(ACCESS_COOKIE)
        if not raw_token:
            return None

        validated = self.get_validated_token(raw_token)
        user = self.get_user(validated)

        self.enforce_csrf(request)
        return user, validated

    def enforce_csrf(self, request):
        """Required because the browser attaches the cookie on its own.

        Without this, any site could POST to this API from a signed-in user's
        browser and the request would carry their credentials.
        """
        if request.method in ("GET", "HEAD", "OPTIONS", "TRACE"):
            return

        check = _CSRFCheck(lambda req: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF failed: {reason}")


def set_auth_cookies(response, access, refresh=None):
    """Attach the tokens to a response.

    Secure is tied to DEBUG: a Secure cookie is dropped over plain HTTP, which
    would make the dev server unusable, while omitting it in production would
    let the token travel in clear text.

    SameSite=Lax stops the cookie riding along with cross-site POSTs, which is
    a second line of defence behind the CSRF token above.
    """

    secure = not settings.DEBUG
    common = {"httponly": True, "secure": secure, "samesite": "Lax", "path": "/"}

    lifetimes = settings.SIMPLE_JWT
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=int(lifetimes["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        **common,
    )
    if refresh:
        response.set_cookie(
            REFRESH_COOKIE,
            refresh,
            max_age=int(lifetimes["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            **common,
        )
    return response


def clear_auth_cookies(response):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(name, path="/")
    return response
