from django.core import signing

# Salt próprio: usar django.contrib.auth.tokens.PasswordResetTokenGenerator
# aqui prenderia a validade deste link ao PASSWORD_RESET_TIMEOUT (1 hora),
# curto demais para confirmar um cadastro. Com signing.dumps/loads temos um
# prazo independente.
CONFIRMATION_SALT = 'accounts.email-confirmation'
CONFIRMATION_MAX_AGE = 60 * 60 * 24 * 3  # 3 dias


def make_confirmation_token(user):
    return signing.dumps(user.pk, salt=CONFIRMATION_SALT)


def read_confirmation_token(token, max_age=CONFIRMATION_MAX_AGE):
    """Devolve o pk do usuário, ou None se o link for inválido/expirado."""
    try:
        return signing.loads(token, salt=CONFIRMATION_SALT, max_age=max_age)
    except signing.BadSignature:
        return None
