from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

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
