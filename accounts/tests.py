
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core import mail, signing
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import PendingSignup

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    AUTHENTICATION_BACKENDS=[
        "accounts.backends.UsernameOrEmailBackend",
    ],
)
class AccountTests(TestCase):
    def setUp(self):
        self.password = "StrongTestPassword!938"
        self.user = User.objects.create_user(
            username="james_test",
            email="james@example.com",
            password=self.password,
        )

    def make_pending_signup(
        self,
        username="pending_student",
        email="pending@example.com",
        password=None,
    ):
        return PendingSignup.objects.create(
            username=username,
            email=email,
            password_hash=make_password(password or self.password),
        )

    def make_verification_token(self, pending):
        return signing.dumps(
            {"pending_signup_id": pending.pk},
            salt="accounts.pending-signup-verification",
        )

    def test_signup_page_loads(self):
        response = self.client.get(reverse("accounts:signup"))
        self.assertEqual(response.status_code, 200)

    def test_signup_creates_pending_registration_and_sends_email(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "new_student",
                "email": "student@example.com",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:verification_sent"),
        )
        self.assertFalse(
            User.objects.filter(username="new_student").exists()
        )

        pending = PendingSignup.objects.get(
            email="student@example.com"
        )
        self.assertNotEqual(pending.password_hash, self.password)
        self.assertTrue(
            User.objects.filter(username="james_test").exists()
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].to,
            ["student@example.com"],
        )
        self.assertIn("verify-email/", mail.outbox[0].body)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_signup_rejects_duplicate_existing_email_case_insensitively(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "another_user",
                "email": "JAMES@EXAMPLE.COM",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username="another_user").exists()
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_signup_rejects_password_mismatch(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "mismatch_user",
                "email": "mismatch@example.com",
                "password1": self.password,
                "password2": "DifferentPassword!938",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username="mismatch_user").exists()
        )
        self.assertFalse(
            PendingSignup.objects.filter(
                username="mismatch_user"
            ).exists()
        )

    def test_signup_reuses_pending_registration_for_same_email(self):
        original = self.make_pending_signup(
            username="original_student",
            email="pending@example.com",
        )

        response = self.client.post(
            reverse("accounts:signup"),
            {
                "username": "updated_student",
                "email": "PENDING@example.com",
                "password1": self.password,
                "password2": self.password,
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:verification_sent"),
        )
        self.assertEqual(
            PendingSignup.objects.filter(
                email__iexact="pending@example.com"
            ).count(),
            1,
        )
        original.refresh_from_db()
        self.assertEqual(original.username, "updated_student")
        self.assertEqual(len(mail.outbox), 1)

    def test_valid_verification_creates_user_and_removes_pending_signup(self):
        pending = self.make_pending_signup(
            username="verified_student",
            email="verified@example.com",
        )
        token = self.make_verification_token(pending)

        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"token": token},
            )
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="verified_student")
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(self.password))
        self.assertFalse(
            PendingSignup.objects.filter(pk=pending.pk).exists()
        )

    def test_invalid_verification_token_does_not_create_user(self):
        response = self.client.get(
            reverse(
                "accounts:verify_email",
                kwargs={"token": "invalid-token"},
            )
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            User.objects.filter(
                username="verified_student"
            ).exists()
        )

    def test_verification_cannot_be_reused_after_pending_signup_is_removed(self):
        pending = self.make_pending_signup(
            username="verified_student",
            email="verified@example.com",
        )
        token = self.make_verification_token(pending)
        url = reverse(
            "accounts:verify_email",
            kwargs={"token": token},
        )

        first_response = self.client.get(url)
        second_response = self.client.get(url)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(
            User.objects.filter(
                username="verified_student"
            ).count(),
            1,
        )

    def test_unverified_user_cannot_log_in(self):
        # A pending signup is not yet a Django User.
        self.make_pending_signup(
            username="unverified_student",
            email="unverified@example.com",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "unverified_student",
                "password": self.password,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_resend_verification_sends_another_email(self):
        self.make_pending_signup()

        response = self.client.post(
            reverse("accounts:resend_verification"),
            {"email": "pending@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify-email/", mail.outbox[0].body)

    def test_resend_verification_does_not_disclose_unknown_email(self):
        response = self.client.post(
            reverse("accounts:resend_verification"),
            {"email": "unknown@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(
            response,
            "If a pending registration exists",
        )

    def test_login_with_username(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "james_test",
                "password": self.password,
            },
        )

        self.assertRedirects(response, reverse("core:library"))

    def test_login_with_email(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "JAMES@example.com",
                "password": self.password,
            },
        )

        self.assertRedirects(response, reverse("core:library"))

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": "james_test",
                "password": "WrongPassword!938",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 405)

    def test_logout_works_with_post(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_reset_page_loads(self):
        response = self.client.get(
            reverse("accounts:password_reset")
        )
        self.assertEqual(response.status_code, 200)

    def test_password_reset_sends_email_for_existing_account(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": self.user.email},
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_done"),
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            "password-reset/confirm/",
            mail.outbox[0].body,
        )

    def test_password_reset_does_not_disclose_unknown_email(self):
        response = self.client.post(
            reverse("accounts:password_reset"),
            {"email": "unknown@example.com"},
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_done"),
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_password_change_requires_login(self):
        response = self.client.get(
            reverse("accounts:password_change")
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:login"),
            response.url,
        )

    def test_password_change_works_for_authenticated_user(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": self.password,
                "new_password1": "AnotherStrongPassword!482",
                "new_password2": "AnotherStrongPassword!482",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("accounts:password_change_done"),
        )

        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password("AnotherStrongPassword!482")
        )
