from django.contrib.auth.backends import ModelBackend


class AllowInactiveAuthenticationBackend(ModelBackend):
    """
    Por padrão, o ModelBackend do Django já recusa autenticar um usuário
    com is_active=False, antes mesmo do formulário de login entrar em ação
    — o site mostraria sempre a mensagem genérica "usuário ou senha
    incorretos", mesmo quando a senha está certa e o problema é só o
    e-mail não confirmado.

    Aqui deixamos autenticar mesmo inativo; quem decide se o login é
    permitido, e com que mensagem, é o confirm_login_allowed() do
    EmailAuthenticationForm (accounts/forms.py).
    """
    def user_can_authenticate(self, user):
        return True
