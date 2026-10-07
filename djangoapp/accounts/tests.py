import os
from pathlib import Path

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


def extract_confirmation_link(email_message):
    import re
    match = re.search(r'https?://testserver(\S+)', email_message.body)
    return match.group(1)


class RegisterTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_register_page_loads(self):
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)

    def test_register_creates_inactive_user_and_sends_confirmation(self):
        response = self.client.post(reverse('accounts:register'), VALID_DATA)

        self.assertContains(response, 'Verifique seu')
        user = User.objects.get()
        # E-mail é salvo em minúsculas e usado como username
        self.assertEqual(user.email, 'maria@email.com')
        self.assertEqual(user.username, 'maria@email.com')
        self.assertEqual(user.first_name, 'Maria')
        # Conta ainda não está ativa, e ninguém fica logado por só se cadastrar
        self.assertFalse(user.is_active)
        self.assertNotIn('_auth_user_id', self.client.session)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['maria@email.com'])
        self.assertIn('confirmar', mail.outbox[0].body.lower())

    def test_confirmation_link_activates_logs_in_and_notifies_owner(self):
        self.client.post(reverse('accounts:register'), VALID_DATA)
        link = extract_confirmation_link(mail.outbox[0])

        response = self.client.get(link, follow=True)

        user = User.objects.get()
        self.assertTrue(user.is_active)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertContains(response, 'class="welcome-overlay"')
        self.assertContains(response, '<p class="welcome-name gradient-text">Maria!</p>')

        # O dono do blog só é avisado quando a conta é confirmada de verdade
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].to, [settings.SIGNUP_NOTIFY_EMAIL])
        self.assertIn('maria@email.com', mail.outbox[1].body)

    def test_confirmation_link_is_single_use(self):
        self.client.post(reverse('accounts:register'), VALID_DATA)
        link = extract_confirmation_link(mail.outbox[0])

        self.client.get(link)
        self.client.logout()
        response = self.client.get(link)

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Link inválido', status_code=400)

    def test_tampered_confirmation_link_rejected(self):
        response = self.client.get(
            reverse('accounts:confirm_email', args=['token-forjado'])
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'Link inválido', status_code=400)

    def test_expired_confirmation_link_rejected(self):
        from unittest.mock import patch

        from accounts.tokens import make_confirmation_token
        user = User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'x', is_active=False,
        )
        # Gera o token com "agora" lá em 1970: qualquer prazo já passou.
        with patch('django.core.signing.time.time', return_value=0):
            old_token = make_confirmation_token(user)

        response = self.client.get(
            reverse('accounts:confirm_email', args=[old_token])
        )
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_register_does_not_leak_whether_email_exists(self):
        User.objects.create_user(
            'existe@email.com', 'existe@email.com', 'x', is_active=True,
        )

        response_new = self.client.post(
            reverse('accounts:register'), {**VALID_DATA, 'email': 'nova@email.com'}
        )
        response_existing = self.client.post(
            reverse('accounts:register'), {**VALID_DATA, 'email': 'existe@email.com'}
        )

        # Mesma página, mesmo status, para quem tem conta e para quem não tem
        self.assertEqual(response_new.status_code, response_existing.status_code)
        self.assertContains(response_new, 'Verifique seu')
        self.assertContains(response_existing, 'Verifique seu')
        self.assertNotContains(response_existing, 'já existe')
        self.assertNotContains(response_existing, 'já tem')

    def test_duplicate_active_email_gets_notice_not_duplicate_account(self):
        User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'senha-antiga-999',
            is_active=True,
        )

        self.client.post(reverse('accounts:register'), VALID_DATA)

        # Não cria uma segunda conta, nem troca a senha da existente
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get()
        self.assertTrue(user.check_password('senha-antiga-999'))
        # Aviso vai para o e-mail da conta já existente, não cria confirmação
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['maria@email.com'])
        self.assertIn('já tem uma conta', mail.outbox[0].body)

    def test_registering_twice_without_confirming_resends_new_link(self):
        self.client.post(reverse('accounts:register'), VALID_DATA)
        first_user_id = User.objects.get().pk

        # Tenta de novo, com senha diferente (ex.: errou a primeira vez)
        self.client.post(reverse('accounts:register'), {
            **VALID_DATA, 'password1': 'outra-senha-456', 'password2': 'outra-senha-456',
        })

        self.assertEqual(User.objects.count(), 1)
        user = User.objects.get()
        self.assertEqual(user.pk, first_user_id)
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password('outra-senha-456'))
        self.assertEqual(len(mail.outbox), 2)  # um link de confirmação por tentativa

    def test_register_rejects_different_passwords(self):
        data = {**VALID_DATA, 'password2': 'outra-senha-456'}

        self.client.post(reverse('accounts:register'), data)

        self.assertFalse(User.objects.exists())


class ResendConfirmationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse('accounts:resend_confirmation')

    def test_resend_to_pending_account_sends_new_link(self):
        User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'x', is_active=False,
        )

        response = self.client.post(self.url, {'email': 'MARIA@email.com'})

        self.assertContains(response, 'Verifique seu')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['maria@email.com'])

    def test_resend_does_not_leak_account_existence(self):
        User.objects.create_user(
            'ativa@email.com', 'ativa@email.com', 'x', is_active=True,
        )

        response_active = self.client.post(self.url, {'email': 'ativa@email.com'})
        response_unknown = self.client.post(self.url, {'email': 'ninguem@email.com'})

        self.assertEqual(response_active.status_code, response_unknown.status_code)
        self.assertContains(response_active, 'Verifique seu')
        self.assertContains(response_unknown, 'Verifique seu')
        # Conta ativa não recebe "link de confirmação" (já está confirmada)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_rate_limit(self):
        for _ in range(5):
            self.client.post(self.url, {'email': 'x@email.com'})
        response = self.client.post(self.url, {'email': 'x@email.com'})
        self.assertEqual(response.status_code, 429)


class LoginRequiresConfirmedEmailTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'senha-forte-123',
            is_active=False,
        )

    def test_cannot_login_before_confirming(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'maria@email.com', 'password': 'senha-forte-123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'Confirme seu e-mail')

    def test_login_page_links_to_resend(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertContains(response, reverse('accounts:resend_confirmation'))


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


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'senha-antiga-123',
            first_name='Maria',
        )
        self.url = reverse('accounts:password_reset')

    def test_login_page_links_to_reset(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertContains(response, reverse('accounts:password_reset'))

    def test_link_expires_in_one_hour(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 3600)

    def test_full_reset_flow(self):
        import re
        response = self.client.post(self.url, {'email': 'MARIA@email.com'})
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['maria@email.com'])
        self.assertIn('vale por 1 hora', email.body)

        link = re.search(r'https?://testserver(\S+)', email.body).group(1)
        # O Django troca o token da URL por um marcador (não vaza em Referer)
        response = self.client.get(link, follow=True)
        self.assertContains(response, 'Crie uma')
        response = self.client.post(response.redirect_chain[-1][0], {
            'new_password1': 'senha-nova-456', 'new_password2': 'senha-nova-456',
        })
        self.assertRedirects(response, reverse('accounts:password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('senha-nova-456'))

        # O mesmo link não funciona uma segunda vez
        response = self.client.get(link, follow=True)
        self.assertContains(response, 'Link inválido')

    def test_email_is_signed_with_blog_name(self):
        from site_setup.models import SiteSetup
        SiteSetup.objects.create(title='Meu Blog', description='x')
        self.client.post(self.url, {'email': 'maria@email.com'})
        self.assertIn('Meu Blog', mail.outbox[0].subject)

    def test_unknown_email_gets_same_page_and_no_email(self):
        response = self.client.post(self.url, {'email': 'ninguem@email.com'})
        # Mesma resposta: não dá para descobrir quem tem conta
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_tampered_link_is_rejected(self):
        response = self.client.get(
            reverse('accounts:password_reset_confirm', args=['MQ', 'token-falso']),
            follow=True,
        )
        self.assertContains(response, 'Link inválido')

    def test_reset_rate_limit(self):
        for _ in range(5):
            self.client.post(self.url, {'email': 'maria@email.com'})
        response = self.client.post(self.url, {'email': 'maria@email.com'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 5)


def image_file(name='foto.png', size=(600, 400), fmt='PNG', exif=None, noise=False):
    from io import BytesIO

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    if noise:
        image = Image.frombytes('RGB', size, os.urandom(size[0] * size[1] * 3))
    else:
        image = Image.new('RGB', size, (200, 30, 90))
    buffer = BytesIO()
    kwargs = {'exif': exif} if exif is not None else {}
    image.save(buffer, fmt, **kwargs)
    return SimpleUploadedFile(name, buffer.getvalue())


class AvatarTests(TestCase):
    def setUp(self):
        import tempfile

        from django.test import override_settings
        cache.clear()
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=Path(self.media))
        self.override.enable()
        self.user = User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'x', first_name='Maria'
        )
        self.client.force_login(self.user)
        self.url = reverse('accounts:avatar')

    def tearDown(self):
        import shutil
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def upload(self, file):
        return self.client.post(self.url, {'avatar': file}, follow=True)

    def avatar(self):
        from accounts.models import Profile
        profile = Profile.objects.filter(user=self.user).first()
        return profile.avatar if profile else None

    def test_requires_login_and_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.upload(image_file()).redirect_chain[0][1], 302)
        self.assertIsNone(self.avatar())

    def test_upload_becomes_square_jpeg_with_random_name(self):
        from PIL import Image
        response = self.upload(image_file('minha foto.png'))
        self.assertContains(response, 'Foto atualizada.')
        avatar = self.avatar()
        self.assertRegex(avatar.name, r'^avatars/[0-9a-f]{32}\.jpg$')
        with Image.open(avatar.path) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.size, (256, 256))
        # A foto aparece no header no lugar da inicial
        self.assertContains(self.client.get('/'), f'src="{avatar.url}"')

    def test_gps_location_is_removed(self):
        from PIL import Image
        exif = Image.Exif()
        exif[0x010F] = 'Celular de teste'                  # fabricante
        exif[0x8825] = {1: 'S', 2: (23.0, 33.0, 1.0)}      # GPS: São Paulo
        self.upload(image_file('celular.jpg', fmt='JPEG', exif=exif))
        with Image.open(self.avatar().path) as image:
            self.assertEqual(len(image.getexif()), 0)

    def test_fake_image_is_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake = SimpleUploadedFile('virus.png', b'MZ isto nao e uma imagem')
        self.upload(fake)
        self.assertFalse(self.avatar())

    def test_too_big_file_is_rejected(self):
        big = image_file('grande.png', size=(1000, 1000), noise=True)  # ~3 MB
        self.assertGreater(big.size, 2 * 1024 * 1024)
        response = self.upload(big)
        self.assertContains(response, 'no máximo 2 MB')
        self.assertFalse(self.avatar())

    def test_image_bomb_is_rejected(self):
        # Arquivo pequeno, mas com 36 milhões de pixels
        bomb = image_file('bomba.png', size=(6000, 6000))
        self.assertLess(bomb.size, 2 * 1024 * 1024)
        response = self.upload(bomb)
        self.assertContains(response, 'grande demais')
        self.assertFalse(self.avatar())

    def test_gif_is_rejected(self):
        response = self.upload(image_file('anim.gif', fmt='GIF'))
        self.assertContains(response, 'PNG, JPG ou WEBP')
        self.assertFalse(self.avatar())

    def test_replace_and_remove_delete_old_files(self):
        self.upload(image_file())
        first = self.avatar().path
        self.upload(image_file())
        self.assertFalse(os.path.exists(first))  # a antiga foi apagada

        second = self.avatar().path
        self.client.post(self.url, {'remove': '1'})
        self.assertFalse(os.path.exists(second))
        self.assertFalse(self.avatar())

    def test_photo_file_is_deleted_with_account(self):
        self.upload(image_file())
        path = self.avatar().path
        self.user.delete()
        self.assertFalse(os.path.exists(path))

    def test_comments_show_author_photo_and_work_without_photo(self):
        from blog.models import Comment, Post
        post = Post.objects.create(
            title='Post', excerpt='r', content='c', is_published=True
        )
        # Autor sem foto (nem perfil): a página não pode quebrar
        sem_foto = User.objects.create_user('s@email.com', 's@email.com', 'x', first_name='Sem')
        Comment.objects.create(post=post, author=sem_foto, text='oi')
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 200)

        self.upload(image_file())
        Comment.objects.create(post=post, author=self.user, text='com foto')
        page = self.client.get(post.get_absolute_url())
        self.assertContains(page, f'src="{self.avatar().url}"')

    def test_upload_rate_limit(self):
        for _ in range(10):
            self.upload(image_file())
        response = self.upload(image_file())
        self.assertContains(response, 'Muitas tentativas')


class WelcomeTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'senha-forte-123',
            first_name='Maria Clara',
        )

    def login(self):
        return self.client.post(reverse('accounts:login'), {
            'username': 'maria@email.com', 'password': 'senha-forte-123',
        }, follow=True)

    def test_welcome_appears_once_after_login(self):
        response = self.login()
        self.assertContains(response, 'class="welcome-overlay"')
        self.assertContains(response, '<p class="welcome-name gradient-text">Maria!</p>')
        # Na página seguinte não aparece de novo
        response = self.client.get(reverse('blog:index'))
        self.assertNotContains(response, 'class="welcome-overlay"')

    def test_home_title_uses_first_name_while_logged_in(self):
        self.login()
        response = self.client.get(reverse('blog:index'))
        self.assertContains(response, 'Seja bem-vindo, <span class="gradient-text">Maria</span>')

    def test_visitor_sees_default_title_and_no_welcome(self):
        response = self.client.get(reverse('blog:index'))
        self.assertNotContains(response, 'class="welcome-overlay"')
        self.assertContains(response, 'Bem-vindo ao')

    def test_wrong_password_does_not_show_welcome(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'maria@email.com', 'password': 'errada',
        })
        self.assertNotContains(response, 'class="welcome-overlay"')
