import json
from unittest.mock import patch, MagicMock
from urllib.error import URLError
from urllib.parse import parse_qs
from django.test import override_settings
from django.core.cache import cache
from rest_framework.test import APITestCase
from customer.models import CustomUser, EmailOTP
from customer.services import send_otp, verify_otp, confirm_account_token
from customer.sms import send_sms_otp, SMSUnavailable
from rest_framework.exceptions import ValidationError


@override_settings(TWILIO_ACCOUNT_SID='AC' + '1'*32, TWILIO_AUTH_TOKEN='test-token', TWILIO_FROM_NUMBER='+15005550006', TWILIO_MESSAGING_SERVICE_SID='')
class SMSOTPTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = CustomUser.objects.create_user('sms@example.com', '+233241234567', password='SMS!Password839', role='customer', is_active=True)

    def test_twilio_request_uses_configured_sender_and_normalized_phone(self):
        response = MagicMock()
        response.read.return_value = b'{"sid":"SM-test","status":"queued"}'
        response.__enter__.return_value = response
        with patch('customer.sms.urlopen', return_value=response) as provider:
            send_sms_otp('0241234567', '123456')
        request = provider.call_args.args[0]
        data = parse_qs(request.data.decode())
        self.assertEqual(data['To'], ['+233241234567'])
        self.assertEqual(data['From'], ['+15005550006'])
        self.assertIn('123456', data['Body'][0])
        self.assertTrue(request.get_header('Authorization').startswith('Basic '))

    def test_sms_registration_and_activation(self):
        with patch('customer.services.send_sms_otp') as sms:
            response = self.client.post('/api/v1/register/request/', {'email':'new-sms@example.com', 'phone_number':'+233241234568', 'role':'customer', 'password':'SMS!Password839', 'password2':'SMS!Password839', 'delivery_channel':'sms'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        user = CustomUser.objects.get(email='new-sms@example.com')
        otp = EmailOTP.objects.get(user=user)
        self.assertEqual(otp.delivery_channel, 'sms')
        self.assertEqual(sms.call_args.args[0], '+233241234568')
        verified = self.client.post('/api/v1/register/verify/', {'email':user.email, 'otp':otp.otp, 'delivery_channel':'sms'}, format='json')
        self.assertEqual(verified.status_code, 200, verified.data)
        confirmed = self.client.post('/api/v1/register/confirm/', {'email':user.email, 'register_token':verified.data['register_token']}, format='json')
        self.assertEqual(confirmed.status_code, 201, confirmed.data)

    def test_password_reset_sms_targets_stored_phone_not_supplied_phone(self):
        with patch('customer.services.send_sms_otp') as sms:
            response = self.client.post('/api/v1/password-reset/request/', {'email':self.user.email, 'delivery_channel':'sms', 'phone_number':'+233241234569'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(sms.call_args.args[0], self.user.phone_number)

    def test_channel_mismatch_cannot_verify_sms_code(self):
        with patch('customer.services.send_sms_otp'):
            send_otp(self.user, 'password_reset', 'sms')
        otp = EmailOTP.objects.get(user=self.user)
        with self.assertRaises(ValidationError):
            verify_otp(self.user.email, otp.otp, 'password_reset', 'email')
        self.assertTrue(verify_otp(self.user.email, otp.otp, 'password_reset', 'sms'))

    def test_phone_change_revokes_sms_confirmation(self):
        with patch('customer.services.send_sms_otp'):
            send_otp(self.user, 'password_reset', 'sms')
        otp = EmailOTP.objects.get(user=self.user)
        token = verify_otp(self.user.email, otp.otp, 'password_reset', 'sms')
        CustomUser.objects.filter(pk=self.user.pk).update(phone_number='+233241234568')
        with self.assertRaises(ValidationError):
            confirm_account_token(token, 'password_reset', lambda user: None)

    def test_failed_delivery_removes_new_sms_code(self):
        with patch('customer.services.send_sms_otp', side_effect=SMSUnavailable()):
            with self.assertRaises(SMSUnavailable):
                send_otp(self.user, 'password_reset', 'sms')
        self.assertFalse(EmailOTP.objects.filter(user=self.user).exists())

    @override_settings(TWILIO_ACCOUNT_SID='')
    def test_unconfigured_sms_registration_does_not_create_account(self):
        response = self.client.post('/api/v1/register/request/', {'email':'missing-sms@example.com', 'phone_number':'+233241234568', 'role':'customer', 'password':'SMS!Password839', 'password2':'SMS!Password839', 'delivery_channel':'sms'}, format='json')
        self.assertEqual(response.status_code, 503, response.data)
        self.assertFalse(CustomUser.objects.filter(email='missing-sms@example.com').exists())

    def test_twilio_failures_do_not_expose_credentials(self):
        with patch('customer.sms.urlopen', side_effect=URLError('secret-provider-detail')):
            with self.assertRaises(SMSUnavailable) as result:
                send_sms_otp(self.user.phone_number, '123456')
        self.assertNotIn('secret-provider-detail', str(result.exception))

    def test_registration_resend_requires_original_password(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post('/api/v1/register/resend/', {'email':self.user.email, 'password':'wrong', 'delivery_channel':'sms'}, format='json')
        self.assertEqual(response.status_code, 400)
        with patch('customer.services.send_sms_otp'):
            response = self.client.post('/api/v1/register/resend/', {'email':self.user.email, 'password':'SMS!Password839', 'delivery_channel':'sms'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(EmailOTP.objects.get(user=self.user).delivery_channel, 'sms')
