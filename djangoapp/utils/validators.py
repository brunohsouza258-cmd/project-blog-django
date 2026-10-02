from django.core.exceptions import ValidationError


def validate_single_line(value):
    # Nomes vão para o assunto de e-mails. Uma quebra de linha ali derruba o
    # envio (erro 500) e é a base do ataque "e-mail header injection".
    if '\n' in value or '\r' in value:
        raise ValidationError('Use apenas uma linha.')


def validate_safe_url(value):
    # Bloqueia links como "javascript:alert(1)", que executariam código
    # quando alguém clicasse no menu.
    allowed = ('http://', 'https://', 'mailto:', '/', '#')
    if not value.strip().lower().startswith(allowed):
        raise ValidationError(
            'Use um link começando com http://, https://, mailto:, / ou #.'
        )
