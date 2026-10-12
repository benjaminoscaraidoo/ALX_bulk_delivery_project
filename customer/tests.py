from unittest.mock import patch
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APITestCase
from customer.models import CustomUser, EmailOTP


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountSecurityTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = CustomUser.objects.create_user('person@example.com', None, password='Original!Password839', role='customer', is_active=True)

    def token(self, purpose='password_reset', user=None):
        user = user or self.user
        EmailOTP.objects.create(user=user, otp='123456', otp_purpose=purpose)
        endpoint = 'register' if purpose == 'registration' else 'password-reset'
        response = self.client.post(f'/api/v1/{endpoint}/verify/', {'email': user.email, 'otp': '123456'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data['register_token' if purpose == 'registration' else 'reset_token']

    def reset(self, token, password='New!StrongPassword742'):
        return self.client.post('/api/v1/password-reset/confirm/', {'reset_token': token, 'new_password': password}, format='json')

    def test_public_admin_route_removed(self):
        self.assertEqual(self.client.post('/api/v1/register/request/superuser/', {}).status_code, 404)

    def test_public_registration_rejects_admin_role(self):
        response = self.client.post('/api/v1/register/request/', {'email': 'admin@example.com', 'role': 'admin', 'password': 'Strong!Password739', 'password2': 'Strong!Password739'}, format='json')
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(CustomUser.objects.filter(email='admin@example.com').exists())

    def test_management_command_creates_active_admin(self):
        with patch.dict('os.environ', {'DJANGO_SUPERUSER_PASSWORD': 'Admin!Password729'}):
            call_command('createsuperuser', email='admin@example.com', phone_number='+233240001111', interactive=False, verbosity=0)
        user = CustomUser.objects.get(email='admin@example.com')
        self.assertTrue(user.is_active and user.is_staff and user.is_superuser)
        self.assertEqual(user.role, 'admin')

    def test_reset_token_cannot_authenticate_api(self):
        token = self.token()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        self.assertEqual(self.client.get('/api/v1/profile/update/').status_code, 401)

    def test_reset_token_is_single_use(self):
        token = self.token()
        self.assertEqual(self.reset(token).status_code, 200)
        self.assertEqual(self.reset(token, 'Another!Password742').status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New!StrongPassword742'))

    def test_weak_password_rejected_without_consuming_token(self):
        token = self.token()
        self.assertEqual(self.reset(token, '12345678').status_code, 400)
        self.assertEqual(self.reset(token).status_code, 200)

    def test_confirmation_expires_after_five_minutes(self):
        with patch('django.core.signing.time.time', return_value=2000000000):
            token = self.token()
        with patch('django.core.signing.time.time', return_value=2000000301):
            self.assertEqual(self.reset(token).status_code, 400)

    def test_registration_is_single_use_and_returns_login_tokens(self):
        self.user.is_active = False
        self.user.save()
        token = self.token('registration')
        payload = {'email': self.user.email, 'register_token': token}
        response = self.client.post('/api/v1/register/confirm/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['tokens']['access'])
        self.assertEqual(self.client.get('/api/v1/profile/update/').status_code, 200)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/v1/register/confirm/', payload, format='json').status_code, 400)

    def test_registration_token_cannot_reset_password(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.reset(self.token('registration')).status_code, 400)

    def test_registration_checks_email_binding(self):
        self.user.is_active = False
        self.user.save()
        token = self.token('registration')
        response = self.client.post('/api/v1/register/confirm/', {'email': 'wrong@example.com', 'register_token': token}, format='json')
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_failed_otp_attempt_is_recorded(self):
        otp = EmailOTP.objects.create(user=self.user, otp='123456', otp_purpose='password_reset')
        response = self.client.post('/api/v1/password-reset/verify/', {'email': self.user.email, 'otp': '654321'}, format='json')
        self.assertEqual(response.status_code, 400)
        otp.refresh_from_db()
        self.assertEqual(otp.attempt_count, 1)
