from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from .sms import normalize_phone
from rest_framework.exceptions import ValidationError


def find_account(identifier):
    if not identifier:
        return None
    users = get_user_model().objects
    try:
        if '@' in identifier:
            return users.get(email__iexact=identifier.strip())
        return users.get(phone_number=normalize_phone(identifier))
    except (get_user_model().DoesNotExist, get_user_model().MultipleObjectsReturned, ValidationError):
        return None


class VerifiedContactBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = username or kwargs.get('identifier') or kwargs.get('email') or kwargs.get('phone_number')
        user = find_account(identifier)
        if user is None:
            get_user_model()().set_password(password or '')
            return None
        verified = user.email_verified if '@' in identifier else user.phone_verified
        if user.check_password(password or '') and verified and self.user_can_authenticate(user):
            return user
        return None
