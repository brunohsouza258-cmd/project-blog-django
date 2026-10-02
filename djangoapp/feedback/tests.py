from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from feedback.models import Feedback


class FeedbackTests(TestCase):
    url = reverse('feedback:feedback')

    def setUp(self):
        cache.clear()

    def test_page_loads(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_feedback_is_saved_and_emailed(self):
        response = self.client.post(self.url, {
            'name': 'Maria',
            'email': 'maria@email.com',
            'message': 'Gostei muito do blog!',
        })

        self.assertRedirects(response, self.url)
        self.assertEqual(Feedback.objects.get().message, 'Gostei muito do blog!')
        # Nos testes o Django guarda os e-mails em mail.outbox em vez de enviar
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [settings.FEEDBACK_EMAIL])
        self.assertIn('Gostei muito do blog!', mail.outbox[0].body)

    def test_empty_message_is_rejected(self):
        self.client.post(self.url, {
            'name': 'Maria', 'email': 'maria@email.com', 'message': '',
        })

        self.assertFalse(Feedback.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_logged_user_gets_fields_prefilled(self):
        user = User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'senha-forte-123',
            first_name='Maria',
        )
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertContains(response, 'value="Maria"')
        self.assertContains(response, 'value="maria@email.com"')


class FeedbackSecurityTests(TestCase):
    url = reverse('feedback:feedback')
    data = {'name': 'Maria', 'email': 'maria@email.com', 'message': 'oi'}

    def setUp(self):
        cache.clear()

    def test_name_with_line_break_is_rejected(self):
        # Antes isso derrubava a página com erro 500 ao montar o e-mail.
        response = self.client.post(
            self.url, {**self.data, 'name': 'Maria\nBcc: spam@x.com'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Use apenas uma linha.')
        self.assertFalse(Feedback.objects.exists())

    def test_honeypot_blocks_bots_silently(self):
        response = self.client.post(
            self.url, {**self.data, 'website': 'http://spam.com'}
        )
        self.assertRedirects(response, self.url)
        self.assertFalse(Feedback.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_rate_limit(self):
        for _ in range(5):
            self.client.post(self.url, self.data)
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(Feedback.objects.count(), 5)
