from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

VALID_DATA = {
    'first_name': 'Maria',
    'email': 'Maria@Email.com',
    'password1': 'senha-forte-123',
    'password2': 'senha-forte-123',
}


class RegisterTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_register_page_loads(self):
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)

    def test_register_creates_user_and_logs_in(self):
        response = self.client.post(reverse('accounts:register'), VALID_DATA)

        self.assertRedirects(response, reverse('blog:index'))
        user = User.objects.get()
        # E-mail é salvo em minúsculas e usado como username
        self.assertEqual(user.email, 'maria@email.com')
        self.assertEqual(user.username, 'maria@email.com')
        self.assertEqual(user.first_name, 'Maria')
        self.assertEqual(
            int(self.client.session['_auth_user_id']), user.pk
        )

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user('maria@email.com', 'maria@email.com', 'x')

        response = self.client.post(reverse('accounts:register'), VALID_DATA)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Já existe uma conta com este e-mail.')
        self.assertEqual(User.objects.count(), 1)

    def test_register_rejects_different_passwords(self):
        data = {**VALID_DATA, 'password2': 'outra-senha-456'}

        self.client.post(reverse('accounts:register'), data)

        self.assertFalse(User.objects.exists())


class LoginLogoutTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'senha-forte-123'
        )

    def test_login_with_email_ignores_case(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'MARIA@email.com',
            'password': 'senha-forte-123',
        })

        self.assertRedirects(response, reverse('blog:index'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'maria@email.com',
            'password': 'errada',
        })

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout(self):
        self.client.login(
            username='maria@email.com', password='senha-forte-123'
        )

        response = self.client.post(reverse('accounts:logout'))

        self.assertRedirects(response, reverse('blog:index'))
        self.assertNotIn('_auth_user_id', self.client.session)


class AccountSecurityTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_login_rate_limit(self):
        url = reverse('accounts:login')
        for _ in range(10):
            self.client.post(url, {'username': 'a@a.com', 'password': 'x'})
        response = self.client.post(
            url, {'username': 'a@a.com', 'password': 'x'}
        )
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'Muitas tentativas', status_code=429)

    def test_register_rate_limit(self):
        url = reverse('accounts:register')
        for i in range(5):
            self.client.post(url, {**VALID_DATA, 'email': f'u{i}@email.com'})
            self.client.logout()
        response = self.client.post(
            url, {**VALID_DATA, 'email': 'u9@email.com'}
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(User.objects.count(), 5)

    def test_name_with_line_break_is_rejected(self):
        self.client.post(
            reverse('accounts:register'),
            {**VALID_DATA, 'first_name': 'Maria\nBcc: x@x.com'},
        )
        self.assertFalse(User.objects.exists())

    def test_login_does_not_redirect_to_other_sites(self):
        User.objects.create_user('m@email.com', 'm@email.com', 'senha-forte-123')
        response = self.client.post(
            reverse('accounts:login') + '?next=https://site-malicioso.com',
            {'username': 'm@email.com', 'password': 'senha-forte-123',
             'next': 'https://site-malicioso.com'},
        )
        self.assertRedirects(response, reverse('blog:index'))

    def test_security_headers(self):
        response = self.client.get(reverse('blog:index'))
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        # Em DEBUG a política é só "report-only"
        self.assertIn("script-src 'self'", response[
            'Content-Security-Policy-Report-Only'
        ])
