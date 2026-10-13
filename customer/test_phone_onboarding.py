from unittest.mock import patch
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase
from customer.models import CustomUser, EmailOTP, CustomerProfile


@override_settings(TWILIO_ACCOUNT_SID='AC'+'1'*32, TWILIO_AUTH_TOKEN='test', TWILIO_FROM_NUMBER='+15005550006', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PhoneOnboardingTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.password = 'Onboarding!Password739'

    def signup(self, channel='sms', role='customer', **contacts):
        with patch('customer.services.send_sms_otp'):
            response = self.client.post('/api/v1/register/request/', {'role':role, 'delivery_channel':channel, 'password':self.password, 'password2':self.password, **contacts}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        user = CustomUser.objects.latest('pk')
        otp = EmailOTP.objects.get(user=user, otp_purpose='registration')
        identifier = contacts['phone_number'] if channel == 'sms' else contacts['email']
        response = self.client.post('/api/v1/register/verify/', {'identifier':identifier, 'otp':otp.otp, 'delivery_channel':channel}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.post('/api/v1/register/confirm/', {'identifier':identifier, 'register_token':response.data['register_token']}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        user.refresh_from_db()
        return user

    def login(self, identifier):
        self.client.force_authenticate(None)
        return self.client.post('/api/v1/auth/login/', {'identifier':identifier, 'password':self.password}, format='json')

    def test_customer_phone_only_signup_and_login(self):
        user = self.signup(phone_number='0241234567')
        self.assertIsNone(user.email)
        self.assertTrue(user.phone_verified)
        self.assertFalse(user.email_verified)
        self.assertEqual(self.login('+233241234567').status_code, 200)
        self.assertEqual(self.client.post('/login/', {'username':'0241234567', 'password':self.password}).status_code, 302)

    def test_sms_signup_cannot_use_optional_unverified_email_to_login(self):
        self.signup(phone_number='+233241234567', email='optional@example.com')
        self.assertEqual(self.login('optional@example.com').status_code, 401)
        self.assertEqual(self.login('+233241234567').status_code, 200)

    def test_email_signup_requires_verified_phone_before_order(self):
        user = self.signup('email', email='email-customer@example.com')
        self.assertTrue(user.email_verified)
        self.assertEqual(self.login(user.email).status_code, 200)
        self.client.force_authenticate(user)
        response = self.client.put('/api/v1/profile/update/', {'first_name':'Ama', 'last_name':'Mensah', 'address':'Accra'}, format='json')
        self.assertFalse(response.data['profile']['is_complete'])
        self.assertEqual(self.client.post('/api/v1/order/create/', {'pickup_address':'Accra'}, format='json').status_code, 403)
        with patch('customer.services.send_sms_otp'):
            response = self.client.post('/api/v1/account/contact/request/', {'delivery_channel':'sms', 'value':'+233241234567'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        otp = EmailOTP.objects.get(user=user, otp_purpose='contact_phone')
        response = self.client.post('/api/v1/account/contact/verify/', {'delivery_channel':'sms', 'otp':otp.otp}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertTrue(user.phone_verified)
        self.assertTrue(user.customer_profile.is_complete)
        self.assertEqual(self.client.post('/api/v1/order/create/', {'pickup_address':'Accra'}, format='json').status_code, 201)

    def test_add_verified_email_to_phone_account(self):
        user = self.signup(phone_number='+233241234567')
        self.client.force_authenticate(user)
        response = self.client.post('/api/v1/account/contact/request/', {'delivery_channel':'email', 'value':'added@example.com'}, format='json')
        self.assertEqual(response.status_code, 200)
        otp = EmailOTP.objects.get(user=user, otp_purpose='contact_email')
        response = self.client.post('/api/v1/account/contact/verify/', {'delivery_channel':'email', 'otp':otp.otp}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.login('added@example.com').status_code, 200)
        self.assertEqual(self.login('+233241234567').status_code, 200)
        self.assertEqual(CustomUser.objects.count(), 1)

    def test_phone_only_driver_requires_profile_and_staff_approval(self):
        user = self.signup(role='driver', phone_number='+233241234567')
        self.client.force_authenticate(user)
        response = self.client.put('/api/v1/profile/update/', {'first_name':'Kwame', 'last_name':'Mensah', 'vehicle_type':'Motorbike', 'vehicle_number':'GR-123', 'license_number':'LIC-123'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        self.assertTrue(user.driverprofile.is_complete)
        self.assertEqual(user.driverprofile.approval_status, 'pending')
        admin = CustomUser.objects.create_superuser('staff@example.com', None, password=self.password)
        self.client.force_authenticate(admin)
        response = self.client.put('/api/v1/admin/driver/approve/', {'identifier':user.phone_number, 'action':'approve'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)

    def test_driver_email_only_signup_rejected(self):
        response = self.client.post('/api/v1/register/request/', {'role':'driver', 'email':'driver@example.com', 'delivery_channel':'email', 'password':self.password, 'password2':self.password}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_phone_recovery_does_not_require_email(self):
        user = self.signup(phone_number='+233241234567')
        with patch('customer.services.send_sms_otp'):
            response = self.client.post('/api/v1/password-reset/request/', {'identifier':user.phone_number, 'delivery_channel':'sms'}, format='json')
        self.assertEqual(response.status_code, 200)
        otp = EmailOTP.objects.get(user=user, otp_purpose='password_reset')
        response = self.client.post('/api/v1/password-reset/verify/', {'identifier':user.phone_number, 'delivery_channel':'sms', 'otp':otp.otp}, format='json')
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/api/v1/password-reset/confirm/', {'reset_token':response.data['reset_token'], 'new_password':'New!OnboardingPassword749'}, format='json')
        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password('New!OnboardingPassword749'))

    def test_unverified_email_cannot_receive_recovery_code(self):
        user = self.signup(phone_number='+233241234567', email='unverified@example.com')
        with patch('customer.services.send_mail') as mail:
            response = self.client.post('/api/v1/password-reset/request/', {'identifier':user.email, 'delivery_channel':'email'}, format='json')
        self.assertEqual(response.status_code, 200)
        mail.assert_not_called()

    def test_cannot_link_contact_owned_by_another_account(self):
        first = self.signup(phone_number='+233241234567')
        CustomUser.objects.create_user('existing@example.com', '+233241234568', role='customer', is_active=True)
        self.client.force_authenticate(first)
        response = self.client.post('/api/v1/account/contact/request/', {'delivery_channel':'email', 'value':'existing@example.com'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_phone_only_registration_cannot_resend_to_missing_email(self):
        user = CustomUser.objects.create_user(None, '+233241234567', password=self.password, role='customer', is_active=False)
        response = self.client.post('/api/v1/register/resend/', {'identifier':user.phone_number, 'password':self.password, 'delivery_channel':'email'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(EmailOTP.objects.filter(user=user).exists())
