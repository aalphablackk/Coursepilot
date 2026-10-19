from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


User = get_user_model()


class UsernameOrEmailBackend(ModelBackend):
    def authenticate(
        self,
        request,
        username=None,
        password=None,
        **kwargs,
    ):
        identifier = username or kwargs.get("email")

        if not identifier or not password:
            return None

        users = User.objects.filter(
            Q(username__iexact=identifier)
            | Q(email__iexact=identifier)
        )

        # Avoid ambiguous email matches.
        if users.count() != 1:
            return None

        user = users.first()

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None