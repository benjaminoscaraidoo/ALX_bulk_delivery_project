from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import EmailOTP
from .utils import generate_otp
from .sms import send_sms_otp, normalize_phone, check_sms_configuration
from .authentication import find_account

def send_otp(user, otp_purpose="", channel="email", destination=None):
    if channel == "email" and not (destination or user.email):
        from rest_framework.exceptions import ValidationError
        raise ValidationError({"email": "This account has no email. Use SMS or add and verify an email after signing in."})
    if channel == "sms":
        check_sms_configuration()
        normalize_phone(destination or user.phone_number)
    with transaction.atomic():
        user = get_user_model().objects.select_for_update().get(pk=user.pk)
        EmailOTP.objects.filter(user=user, otp_purpose=otp_purpose).delete()
        code = generate_otp()
        destination = normalize_phone(destination or user.phone_number) if channel == "sms" else (destination or user.email)
        otp = EmailOTP.objects.create(user=user, otp=code, otp_purpose=otp_purpose, delivery_channel=channel, destination=destination)
    if channel == "sms":
        try:
            send_sms_otp(destination, code)
        except Exception:
            EmailOTP.objects.filter(pk=otp.pk).delete()
            raise
        return
    send_mail(subject="Your Verification Code",
              message=f"Your OTP is {code}. It expires in 5 minutes.",
              from_email=settings.EMAIL_HOST_USER, recipient_list=[user.email])

CONFIRMATION_SALT = 'bulk-delivery.account-confirmation'


def verify_otp(identifier, code, purpose, channel="email", user_id=None):
    from django.core import signing
    from django.db import transaction
    from rest_framework.exceptions import PermissionDenied, ValidationError

    with transaction.atomic():
        found = get_user_model().objects.filter(pk=user_id).first() if user_id else find_account(identifier)
        user = get_user_model().objects.select_for_update().filter(pk=found.pk).first() if found else None
        if not user:
            raise ValidationError("Invalid or expired OTP.")
        otp = EmailOTP.objects.select_for_update().filter(
            user=user, otp_purpose=purpose, is_verified=False, delivery_channel=channel
        ).last()
        if not otp or otp.is_expired():
            raise ValidationError('Invalid or expired OTP.')
        if purpose != "contact_email" and otp.delivery_channel == "email" and otp.destination and (user.email or "").lower() != otp.destination.lower():
            raise ValidationError("Email changed. Request a new code.")
        if purpose != "contact_phone" and otp.delivery_channel == "sms" and normalize_phone(user.phone_number) != otp.destination:
            raise ValidationError("Phone number changed. Request a new code.")
        if otp.is_locked():
            raise PermissionDenied('Too many attempts.')
        if otp.otp != code:
            otp.attempt_count += 1
            otp.save(update_fields=['attempt_count'])
            invalid = True
        else:
            otp.is_verified = True
            otp.save(update_fields=['is_verified'])
            invalid = False
            token = signing.dumps({'otp_id': otp.pk, 'purpose': purpose}, salt=CONFIRMATION_SALT)
    # Raise after committing the failed attempt.
    if invalid:
        raise ValidationError('Invalid OTP.')
    return token


def confirm_account_token(token, purpose, action):
    from django.core import signing
    from django.db import transaction
    from django.contrib.auth import get_user_model
    from rest_framework.exceptions import ValidationError

    try:
        payload = signing.loads(token, salt=CONFIRMATION_SALT, max_age=300)
    except signing.BadSignature:
        raise ValidationError('Invalid or expired confirmation token.')
    if not isinstance(payload, dict) or payload.get('purpose') != purpose:
        raise ValidationError('Invalid confirmation purpose.')
    with transaction.atomic():
        try:
            user_id = EmailOTP.objects.filter(pk=payload.get('otp_id'), otp_purpose=purpose).values_list('user_id', flat=True).first()
            user = get_user_model().objects.select_for_update().get(pk=user_id)
            otp = EmailOTP.objects.select_for_update().get(
                pk=payload.get('otp_id'), user=user, otp_purpose=purpose, is_verified=True
            )
        except (EmailOTP.DoesNotExist, get_user_model().DoesNotExist, TypeError, ValueError):
            raise ValidationError('Confirmation token has already been used or revoked.')
        if purpose != "contact_email" and otp.delivery_channel == "email" and otp.destination and (user.email or "").lower() != otp.destination.lower():
            raise ValidationError("Email changed. Request a new code.")
        if purpose != "contact_phone" and otp.delivery_channel == "sms" and normalize_phone(user.phone_number) != otp.destination:
            raise ValidationError("Phone number changed. Request a new code.")
        if purpose == "registration":
            if otp.delivery_channel == "sms":
                user.phone_verified = True
            else:
                user.email_verified = True
        elif purpose == "contact_email":
            user.email = otp.destination
            user.email_verified = True
        elif purpose == "contact_phone":
            user.phone_number = otp.destination
            user.phone_verified = True
        action(user)
        otp.delete()
    return user
