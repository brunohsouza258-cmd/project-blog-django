from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from accounts.forms import EmailAuthenticationForm, RegisterForm
from utils.rate_limit import is_rate_limited

TOO_MANY_ATTEMPTS = 'Muitas tentativas seguidas. Espere alguns minutos.'


def register(request):
    # Quem já está logado não precisa criar conta.
    if request.user.is_authenticated:
        return redirect('blog:index')

    form = RegisterForm(request.POST or None)

    # Até 5 cadastros por hora por IP: dificulta robôs criando contas falsas.
    if request.method == 'POST' and is_rate_limited(
        request, 'register', limit=5, window=60 * 60
    ):
        form.add_error(None, TOO_MANY_ATTEMPTS)
        return render(
            request, 'accounts/register.html', {'form': form}, status=429
        )

    if request.method == 'POST' and form.is_valid():
        user = form.save()
        # Já entra na conta logo depois do cadastro.
        login(request, user)

        # Avisa o dono do blog que alguém criou uma conta.
        send_mail(
            subject=f'[Blog] Nova conta: {user.first_name}',
            message=f'Nome: {user.first_name}\nE-mail: {user.email}',
            from_email=None,  # usa o DEFAULT_FROM_EMAIL do settings.py
            recipient_list=[settings.SIGNUP_NOTIFY_EMAIL],
            fail_silently=True,
        )

        messages.success(
            request, f'Conta criada! Bem-vindo, {user.first_name}.'
        )
        return redirect('blog:index')

    return render(request, 'accounts/register.html', {'form': form})


class EmailLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = EmailAuthenticationForm
    # Usuário já logado que abrir /conta/entrar/ é mandado para a home.
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        # Até 10 tentativas de login a cada 10 minutos por IP: impede que
        # alguém fique testando milhares de senhas (ataque de força bruta).
        if is_rate_limited(request, 'login', limit=10, window=60 * 10):
            form = self.get_form()
            form.add_error(None, TOO_MANY_ATTEMPTS)
            return self.render_to_response(
                self.get_context_data(form=form), status=429
            )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Você entrou na sua conta.')
        return super().form_valid(form)


class AccountLogoutView(LogoutView):
    # O logout só aceita POST (proteção contra sair da conta só por abrir
    # um link). Por isso o botão "Sair" do header é um <form>.
    def post(self, request, *args, **kwargs):
        messages.info(request, 'Você saiu da sua conta.')
        return super().post(request, *args, **kwargs)
