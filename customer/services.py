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