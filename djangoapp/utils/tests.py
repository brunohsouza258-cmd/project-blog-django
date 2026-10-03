from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from utils.validators import validate_safe_url, validate_single_line


class ValidatorTests(SimpleTestCase):
    def test_single_line(self):
        validate_single_line('Maria Silva')
        for value in ('Maria\nBcc: x@x.com', 'Maria\rX'):
            with self.assertRaises(ValidationError):
                validate_single_line(value)

    def test_safe_url(self):
        for url in ('https://x.com', 'http://x.com', '/sobre/', '#posts',
                    'mailto:a@a.com'):
            validate_safe_url(url)
        for url in ('javascript:alert(1)', ' JavaScript:alert(1)',
                    'data:text/html,oi', 'vbscript:x'):
            with self.assertRaises(ValidationError):
                validate_safe_url(url)


class ClientIpTests(SimpleTestCase):
    def request(self, remote, forwarded=None):
        from django.test import RequestFactory
        extra = {'REMOTE_ADDR': remote}
        if forwarded:
            extra['HTTP_X_FORWARDED_FOR'] = forwarded
        return RequestFactory().get('/', **extra)

    def test_without_proxy_ignores_forwarded_header(self):
        from django.test import override_settings
        from utils.rate_limit import client_ip
        with override_settings(NUM_PROXIES=0):
            # Visitante tentando se passar por outro IP
            req = self.request('9.9.9.9', forwarded='1.2.3.4')
            self.assertEqual(client_ip(req), '9.9.9.9')

    def test_behind_one_proxy_uses_ip_added_by_proxy(self):
        from django.test import override_settings
        from utils.rate_limit import client_ip
        with override_settings(NUM_PROXIES=1):
            # O visitante forjou "1.2.3.4"; o nginx acrescentou o IP real no fim
            req = self.request('10.0.0.2', forwarded='1.2.3.4, 9.9.9.9')
            self.assertEqual(client_ip(req), '9.9.9.9')
            # Sem cabeçalho, cai no REMOTE_ADDR
            self.assertEqual(client_ip(self.request('10.0.0.2')), '10.0.0.2')


class AdminAndMediaSecurityTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_admin_login_rate_limit(self):
        url = reverse('admin:login')
        for _ in range(5):
            response = self.client.post(url, {'username': 'x', 'password': 'y'})
            self.assertEqual(response.status_code, 200)
        response = self.client.post(url, {'username': 'x', 'password': 'y'})
        self.assertEqual(response.status_code, 429)
        # Abrir a página (GET) continua funcionando
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_media_blocks_path_traversal(self):
        # 400 (caminho suspeito) ou 404: o importante é nunca servir o arquivo
        for path in ('/media/../../etc/passwd', '/media/..%2F..%2Fetc/passwd'):
            response = self.client.get(path)
            self.assertIn(response.status_code, (400, 404), path)
            self.assertNotIn(b'root:', response.content)


class PhoneTests(TestCase):
    def test_phone_validator(self):
        from utils.validators import validate_phone
        for ok in ('(11) 95639-6972', '11956396972', '+55 11 95639-6972'):
            validate_phone(ok)
        for bad in ('abc', '123', 'javascript:alert(1)', '(11) 9563-69<b>'):
            with self.assertRaises(ValidationError):
                validate_phone(bad)

    def test_phone_in_footer_with_whatsapp_link_and_in_ai(self):
        from django.test import RequestFactory

        from chatbot.context import build_system_prompt
        from site_setup.models import SiteSetup
        SiteSetup.objects.create(
            title='Blog', description='x', contact_phone='(11) 95639-6972'
        )
        response = self.client.get('/')
        self.assertContains(response, 'href="https://wa.me/5511956396972"')
        self.assertContains(response, '(11) 95639-6972')
        prompt = build_system_prompt(RequestFactory().get('/'), '')
        self.assertIn('(11) 95639-6972', prompt)

    def test_no_phone_no_whatsapp(self):
        self.assertNotContains(self.client.get('/'), 'wa.me')
