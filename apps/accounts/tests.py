"""Authentication hardening.

Covers the three changes that matter: tokens are no longer reachable from
JavaScript, sign-in cannot be hammered, and signing out actually ends the
session rather than just forgetting it locally.
"""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.testing import make_organization, make_user

from .authentication import ACCESS_COOKIE, REFRESH_COOKIE

PASSWORD = "TestPass!2026"


class CookieSessionTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        self.user = make_user("teacher1", organization=self.org)

    def login(self):
        return self.client.post(
            reverse("login"), {"username": "teacher1", "password": PASSWORD}
        )

    def test_signing_in_sets_httponly_cookies(self):
        """A token JavaScript can read is a token an XSS can steal."""
        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for name in (ACCESS_COOKIE, REFRESH_COOKIE):
            with self.subTest(cookie=name):
                cookie = response.cookies[name]
                self.assertTrue(cookie["httponly"])
                self.assertEqual(cookie["samesite"], "Lax")

    def test_the_cookie_alone_authenticates_a_read(self):
        self.login()
        # No Authorization header is set anywhere in this test.
        response = self.client.get(reverse("session"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "teacher1")

    def test_an_anonymous_read_is_still_rejected(self):
        self.assertEqual(
            self.client.get(reverse("session")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_a_write_without_a_csrf_token_is_refused(self):
        """The browser attaches the cookie by itself, so without this any site
        could POST to the API carrying a signed-in user's credentials."""
        self.login()

        enforcing = self.client_class(enforce_csrf_checks=True)
        enforcing.cookies = self.client.cookies

        response = enforcing.post(reverse("attendance-bulk"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_the_header_flow_still_works_for_api_clients(self):
        """Mobile and server-to-server callers have no cookie jar."""
        token = self.login().data["access"]

        bare = self.client_class()
        response = bare.get(reverse("session"), HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_deactivated_account_cannot_sign_in(self):
        self.user.is_active = False
        self.user.save()

        self.assertEqual(self.login().status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_bad_username_and_a_bad_password_look_identical(self):
        """Otherwise the response reveals which accounts exist."""
        wrong_user = self.client.post(
            reverse("login"), {"username": "nobody", "password": PASSWORD}
        )
        wrong_pass = self.client.post(
            reverse("login"), {"username": "teacher1", "password": "wrong"}
        )

        self.assertEqual(wrong_user.status_code, wrong_pass.status_code)
        self.assertEqual(wrong_user.data, wrong_pass.data)


class SignOutTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        make_user("teacher1", organization=self.org)
        self.tokens = self.client.post(
            reverse("login"), {"username": "teacher1", "password": PASSWORD}
        ).data

    def test_signing_out_clears_the_cookies(self):
        response = self.client.post(reverse("logout"), {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.cookies[ACCESS_COOKIE].value, "")
        self.assertEqual(response.cookies[REFRESH_COOKIE].value, "")

    def test_the_refresh_token_stops_working_after_sign_out(self):
        """Without blacklisting, a copy taken beforehand would keep minting
        access tokens for its full seven-day life."""
        self.client.post(reverse("logout"), {})

        bare = self.client_class()
        response = bare.post(
            reverse("cookie-refresh"), {"refresh": self.tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_signing_out_twice_is_not_an_error(self):
        self.client.post(reverse("logout"), {})
        self.assertEqual(
            self.client.post(reverse("logout"), {}).status_code, status.HTTP_200_OK
        )


class RefreshRotationTests(APITestCase):
    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        make_user("teacher1", organization=self.org)
        self.tokens = self.client.post(
            reverse("login"), {"username": "teacher1", "password": PASSWORD}
        ).data

    def test_refreshing_rotates_the_token(self):
        """A stolen refresh token must stop working once the real user
        refreshes."""
        first = self.client.post(reverse("cookie-refresh"), {})
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        bare = self.client_class()
        reused = bare.post(
            reverse("cookie-refresh"), {"refresh": self.tokens["refresh"]}, format="json"
        )
        self.assertEqual(reused.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_a_garbage_token_clears_the_cookies(self):
        """Leaving a dead token in the browser makes every later request fail
        in the same confusing way."""
        bare = self.client_class()
        response = bare.post(
            reverse("cookie-refresh"), {"refresh": "not-a-token"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.cookies[ACCESS_COOKIE].value, "")


class LoginThrottleTests(APITestCase):
    """Sign-in is the one endpoint reachable without an account."""

    def setUp(self):
        self.org = make_organization("ORGA", "School A")
        make_user("teacher1", organization=self.org)

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()   # throttle counters are cached; leaking them breaks later tests

    def test_repeated_failures_are_throttled(self):
        codes = [
            self.client.post(
                reverse("login"), {"username": "teacher1", "password": "wrong"}
            ).status_code
            for _ in range(12)
        ]

        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codes)
        # The limit is 10/min, so the first few must still have been answered
        # normally rather than the whole burst being blocked.
        self.assertIn(status.HTTP_401_UNAUTHORIZED, codes[:10])
