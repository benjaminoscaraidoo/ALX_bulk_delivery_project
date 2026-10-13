import base64
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError
import phonenumbers
from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError


class SMSUnavailable(APIException):
    status_code = 503
    default_detail = 'SMS could not be sent. Please try again or choose email.'


def normalize_phone(value):
    try:
        number = phonenumbers.parse(value or '', 'GH')
        if not phonenumbers.is_valid_number(number):
            raise ValueError()
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    except (phonenumbers.NumberParseException, ValueError):
        raise ValidationError({'phone_number': 'Enter a valid phone number with country code, for example +233….'})


def check_sms_configuration():
    if not re.fullmatch(r'AC[0-9a-fA-F]{32}', settings.TWILIO_ACCOUNT_SID) or not settings.TWILIO_AUTH_TOKEN or not (settings.TWILIO_FROM_NUMBER or settings.TWILIO_MESSAGING_SERVICE_SID):
        raise SMSUnavailable('SMS is not configured yet. Please choose email.')


def send_sms_otp(phone, code):
    check_sms_configuration()
    data = {'To': normalize_phone(phone), 'Body': f'OY Delivery Services: your verification code is {code}. It expires in 5 minutes. Do not share this code.'}
    if settings.TWILIO_MESSAGING_SERVICE_SID:
        data['MessagingServiceSid'] = settings.TWILIO_MESSAGING_SERVICE_SID
    else:
        data['From'] = settings.TWILIO_FROM_NUMBER
    credential = base64.b64encode(f'{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}'.encode()).decode()
    request = Request(f'https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json', data=urlencode(data).encode(), headers={'Authorization': 'Basic ' + credential, 'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    try:
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
        if not result.get('sid') or result.get('status') in ['failed', 'undelivered']:
            raise SMSUnavailable()
    except (URLError, TimeoutError, OSError, ValueError, TypeError):
        raise SMSUnavailable()
