from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
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

    def test_register_notifies_owner_by_email(self):
        self.client.post(reverse('accounts:register'), VALID_DATA)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [settings.SIGNUP_NOTIFY_EMAIL])
        self.assertIn('maria@email.com', mail.outbox[0].body)

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


class ProfileCrudTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'senha-forte-123',
            first_name='Maria Clara',
        )
        self.client.force_login(self.user)

    def test_pages_require_login(self):
        self.client.logout()
        for name in ('profile', 'password_change', 'delete'):
            response = self.client.get(reverse(f'accounts:{name}'))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse('accounts:login'), response.url)

    def test_profile_shows_first_name_and_data(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertContains(response, 'Olá, <span class="gradient-text">Maria</span>')
        self.assertContains(response, 'value="maria@email.com"')

    def test_edit_name_and_email(self):
        response = self.client.post(reverse('accounts:profile'), {
            'first_name': 'Ana Paula', 'email': 'Ana@Email.com',
        })
        self.assertRedirects(response, reverse('accounts:profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Ana Paula')
        # E-mail em minúsculas e usado também para o login
        self.assertEqual(self.user.email, 'ana@email.com')
        self.assertEqual(self.user.username, 'ana@email.com')
        self.client.logout()
        self.assertTrue(self.client.login(
            username='ana@email.com', password='senha-forte-123'
        ))

    def test_cannot_use_email_of_another_account(self):
        User.objects.create_user('outro@email.com', 'outro@email.com', 'x')
        response = self.client.post(reverse('accounts:profile'), {
            'first_name': 'Maria', 'email': 'outro@email.com',
        })
        self.assertContains(response, 'Já existe uma conta com este e-mail.')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'maria@email.com')

    def test_name_is_required_and_single_line(self):
        for name in ('', 'Maria\nBcc: x@x.com'):
            self.client.post(reverse('accounts:profile'), {
                'first_name': name, 'email': 'maria@email.com',
            })
            self.user.refresh_from_db()
            self.assertEqual(self.user.first_name, 'Maria Clara')

    def test_change_password_keeps_user_logged_in(self):
        response = self.client.post(reverse('accounts:password_change'), {
            'old_password': 'senha-forte-123',
            'new_password1': 'nova-senha-456',
            'new_password2': 'nova-senha-456',
        })
        self.assertRedirects(response, reverse('accounts:profile'))
        self.assertIn('_auth_user_id', self.client.session)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('nova-senha-456'))

    def test_change_password_requires_current_password(self):
        self.client.post(reverse('accounts:password_change'), {
            'old_password': 'errada',
            'new_password1': 'nova-senha-456',
            'new_password2': 'nova-senha-456',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('senha-forte-123'))

    def test_delete_with_wrong_password_keeps_account(self):
        response = self.client.post(reverse('accounts:delete'), {'password': 'errada'})
        self.assertContains(response, 'Senha incorreta.')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_account(self):
        response = self.client.post(
            reverse('accounts:delete'), {'password': 'senha-forte-123'}
        )
        self.assertRedirects(response, reverse('blog:index'))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_delete_is_rate_limited(self):
        for _ in range(5):
            self.client.post(reverse('accounts:delete'), {'password': 'errada'})
        response = self.client.post(
            reverse('accounts:delete'), {'password': 'senha-forte-123'}
        )
        self.assertEqual(response.status_code, 429)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_admin_cannot_delete_own_account_here(self):
        self.user.is_staff = True
        self.user.save()
        response = self.client.post(
            reverse('accounts:delete'), {'password': 'senha-forte-123'}
        )
        self.assertRedirects(response, reverse('accounts:profile'))
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_welcome_message_uses_first_name(self):
        self.client.logout()
        response = self.client.post(reverse('accounts:register'), {
            'first_name': 'João Pedro Silva', 'email': 'joao@email.com',
            'password1': 'senha-forte-123', 'password2': 'senha-forte-123',
        }, follow=True)
        self.assertContains(response, 'Conta criada! Bem-vindo, João.')
