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


def validate_phone(value):
    # Só números e a pontuação comum de telefone: nada de letras ou links.
    allowed = set('0123456789 ()-+')
    digits = [c for c in value if c.isdigit()]
    if set(value) - allowed or not 10 <= len(digits) <= 13:
        raise ValidationError('Use um telefone como (11) 95639-6972.')
