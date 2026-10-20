
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .forms import SignUpForm
from .models import PendingSignup
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

VERIFICATION_MAX_AGE = 60 * 60 * 24
VERIFICATION_SALT = "accounts.pending-signup-verification"
RESEND_COOLDOWN_SECONDS = 60


def _send_verification_email(request, pending):
    token = signing.dumps(
        {"pending_signup_id": pending.pk},
        salt=VERIFICATION_SALT,
    )
    verification_url = request.build_absolute_uri(
        reverse(
            "accounts:verify_email",
            kwargs={"token": token},
        )
    )

    send_mail(
        subject="Verify your CoursePilot account",
        message=(
            f"Hi {pending.username},\n\n"
            "Thanks for signing up for CoursePilot. "
            "Verify your email address within 24 hours using this link:\n\n"
            f"{verification_url}\n\n"
            "If you did not request this, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[pending.email],
        fail_silently=False,
    )

def _resend_is_throttled(pending):
    sent_at = pending.last_verification_sent_at

    if sent_at is None:
        return False

    elapsed = (timezone.now() - sent_at).total_seconds()
    return elapsed < RESEND_COOLDOWN_SECONDS

def signup(request):
    if request.user.is_authenticated:
        return redirect("core:library")

    error_message = None

    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            email = form.cleaned_data["email"]
            password_hash = form.save(commit=False).password

            if User.objects.filter(username__iexact=username).exists():
                form.add_error(
                    "username",
                    "This username is already in use.",
                )
            else:
                # Reuse a pending registration for the same email.
                pending = PendingSignup.objects.filter(
                    email__iexact=email
                ).first()

                # Prevent a pending username from conflicting with
                # another registration.
                pending_usernames = PendingSignup.objects.filter(
                    username__iexact=username
                )

                if pending:
                    pending_usernames = pending_usernames.exclude(pk=pending.pk)

                username_conflict = pending_usernames.exists()

                if username_conflict:
                    form.add_error(
                        "username",
                        "This username is already awaiting verification.",
                    )
                else:
                    if pending:
                        pending.username = username
                        pending.email = email
                        pending.password_hash = password_hash
                        pending.save(
                            update_fields=[
                                "username",
                                "email",
                                "password_hash",
                                "updated_at",
                            ]
                        )
                    else:
                        pending = PendingSignup.objects.create(
                            username=username,
                            email=email,
                            password_hash=password_hash,
                        )

                    try:
                        _send_verification_email(request, pending)
                    except Exception:
                        # The pending record remains recoverable. The user
                        # can request another verification email.
                        logger.exception("CoursePilot verification email failed")
                        error_message = (
                            "We couldn't send the verification email right "
                            "now. Please check the email address and try "
                            "resending the verification email."
                        )
                    else:
                        return redirect("accounts:verification_sent")
    else:
        form = SignUpForm()

    return render(
        request,
        "accounts/signup.html",
        {"form": form, "email_error": error_message},
    )


def verification_sent(request):
    return render(request, "accounts/verification_sent.html")


def resend_verification(request):
    message = (
        "If a pending registration exists for that email, "
        "we'll send a verification link."
    )

    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        if email:
            pending = PendingSignup.objects.filter(
                email__iexact=email
            ).first()

            if pending:
                account_exists = User.objects.filter(
                    email__iexact=email,
                    is_active=True,
                ).exists()

                if (
                    not account_exists
                    and not _resend_is_throttled(pending)
                ):
                    try:
                        _send_verification_email(request, pending)
                    except Exception:
                        logger.exception(
                            "CoursePilot resend verification email failed"
                        )
                    else:
                        pending.last_verification_sent_at = timezone.now()
                        pending.save(
                            update_fields=["last_verification_sent_at"]
                        )

        return render(
            request,
            "accounts/resend_verification.html",
            {"message": message},
        )

    return render(
        request,
        "accounts/resend_verification.html",
        {"message": None},
    )

def verify_email(request, token):
    try:
        data = signing.loads(
            token,
            salt=VERIFICATION_SALT,
            max_age=VERIFICATION_MAX_AGE,
        )
        pending = PendingSignup.objects.get(
            pk=data["pending_signup_id"]
        )
    except (
        signing.BadSignature,
        signing.SignatureExpired,
        PendingSignup.DoesNotExist,
        KeyError,
        TypeError,
        ValueError,
    ):
        return render(
            request,
            "accounts/verification_invalid.html",
            status=400,
        )

    if User.objects.filter(
        email__iexact=pending.email
    ).exists() or User.objects.filter(
        username__iexact=pending.username
    ).exists():
        pending.delete()
        return render(
            request,
            "accounts/verification_invalid.html",
            status=400,
        )

    with transaction.atomic():
        user = User(
            username=pending.username,
            email=pending.email,
            password=pending.password_hash,
            is_active=True,
        )
        user.save()
        pending.delete()

    return render(request, "accounts/verification_success.html")
