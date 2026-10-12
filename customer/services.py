from django.core.mail import send_mail
from django.conf import settings
from .models import EmailOTP
from .utils import generate_otp

def send_otp(user, otp_purpose = ""):

    # Delete old OTPs
    EmailOTP.objects.filter(user=user, otp_purpose=otp_purpose).delete()

    code = generate_otp()

    EmailOTP.objects.create(
        user=user,
        otp=code,
        otp_purpose=otp_purpose
    )

    send_mail(
        subject="Your Verification Code",
        message=f"Your OTP is {code}. It expires in 5 minutes.",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[user.email],
    )

CONFIRMATION_SALT = 'bulk-delivery.account-confirmation'


def verify_otp(email, code, purpose):
    from django.core import signing
    from django.db import transaction
    from rest_framework.exceptions import PermissionDenied, ValidationError

    with transaction.atomic():
        otp = EmailOTP.objects.select_for_update().filter(
            user__email=email, otp_purpose=purpose, is_verified=False
        ).last()
        if not otp or otp.is_expired():
            raise ValidationError('Invalid or expired OTP.')
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
            otp = EmailOTP.objects.select_for_update().get(
                pk=payload.get('otp_id'), otp_purpose=purpose, is_verified=True
            )
            user = get_user_model().objects.select_for_update().get(pk=otp.user_id)
        except (EmailOTP.DoesNotExist, get_user_model().DoesNotExist, TypeError, ValueError):
            raise ValidationError('Confirmation token has already been used or revoked.')
        action(user)
        otp.delete()
    return user
