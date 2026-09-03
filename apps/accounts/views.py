from django.contrib.auth import authenticate
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    set_auth_cookies,
)
from .models import User
from .serializers import UserRegistrationSerializer, UserSerializer


def _session_payload(user):
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone_number": user.phone_number,
        "role": user.role,
        "organization": user.organization.id if user.organization else None,
    }


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "register"

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "User registered successfully.",
                    "user": UserSerializer(user).data,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginView(APIView):
    """Sign in and receive the session as httpOnly cookies.

    The tokens are also returned in the body, because a mobile or server-side
    client has no cookie jar and needs the header flow. A browser should ignore
    them and rely on the cookies, which JavaScript cannot read.

    Throttled: this is the one endpoint reachable without an account, so it is
    the one an attacker can hammer.
    """

    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        user = authenticate(
            username=request.data.get("username"),
            password=request.data.get("password"),
        )

        if user is None:
            # One message for a bad username and a bad password alike, so the
            # response cannot be used to discover which accounts exist.
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "This account has been deactivated."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        response = Response(
            {
                "message": "Login successful.",
                "refresh": str(refresh),
                "access": access,
                "user": _session_payload(user),
            },
            status=status.HTTP_200_OK,
        )
        return set_auth_cookies(response, access, str(refresh))


class LogoutView(APIView):
    """Sign out: blacklist the refresh token and clear the cookies.

    Without blacklisting, a refresh token captured before sign-out would keep
    minting access tokens for its full lifetime.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("refresh") or request.COOKIES.get(REFRESH_COOKIE)

        if token:
            try:
                RefreshToken(token).blacklist()
            except TokenError:
                # Already expired or already blacklisted. Signing out twice is
                # not an error the user should ever see.
                pass

        response = Response({"message": "Signed out."}, status=status.HTTP_200_OK)
        return clear_auth_cookies(response)


class SessionView(APIView):
    """Who am I? Used by the front end on load, since it can no longer read the
    token to find out."""

    def get(self, request):
        return Response(_session_payload(request.user))


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CookieTokenRefreshView(APIView):
    """Exchange the refresh cookie for a fresh access cookie."""

    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("refresh") or request.COOKIES.get(REFRESH_COOKIE)
        if not token:
            return Response(
                {"error": "No refresh token."}, status=status.HTTP_401_UNAUTHORIZED
            )

        def expired():
            # Clear the cookies too: leaving a dead refresh token in the browser
            # makes every later request fail in the same confusing way.
            return clear_auth_cookies(
                Response({"error": "Session expired."},
                         status=status.HTTP_401_UNAUTHORIZED)
            )

        try:
            refresh = RefreshToken(token)
        except TokenError:
            return expired()

        # The caller is anonymous on this endpoint, so the account comes from
        # the token's own claim rather than request.user.
        user = User.objects.filter(pk=refresh.payload.get("user_id")).first()
        if user is None or not user.is_active:
            return expired()

        # ROTATE_REFRESH_TOKENS is on: retire the presented token and issue a
        # fresh pair, so a stolen refresh token stops working the moment the
        # real user refreshes.
        try:
            refresh.blacklist()
        except AttributeError:
            # Blacklisting needs the token_blacklist app; without it rotation
            # is a no-op rather than a failure.
            pass

        rotated = RefreshToken.for_user(user)
        access = str(rotated.access_token)

        response = Response({"access": access}, status=status.HTTP_200_OK)
        return set_auth_cookies(response, access, str(rotated))
