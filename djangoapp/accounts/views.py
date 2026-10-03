from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordChangeView, PasswordResetCompleteView,
    PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView,
)
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from accounts.context_processors import display_name
from accounts.forms import (
    DeleteAccountForm, EmailAuthenticationForm, EmailPasswordResetForm,
    ProfileForm, RegisterForm,
)
from site_setup.models import SiteSetup
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

        first_name = display_name(request)['display_name']
        messages.success(request, f'Conta criada! Bem-vindo, {first_name}.')
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


@login_required
def profile(request):
    """Minha conta: mostra e edita nome e e-mail (o R e o U do CRUD)."""
    form = ProfileForm(request.POST or None, instance=request.user)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Dados atualizados.')
        return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {'form': form})


class AccountPasswordChangeView(PasswordChangeView):
    # O PasswordChangeView do Django confere a senha atual, aplica os
    # validadores de senha e mantém o usuário logado depois da troca.
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, 'Senha alterada.')
        return super().form_valid(form)


@login_required
@require_http_methods(['GET', 'POST'])
def delete_account(request):
    """Exclui a conta depois de confirmar a senha (o D do CRUD)."""
    # Admin não se exclui por aqui: perderia o acesso ao painel sem querer.
    if request.user.is_staff:
        messages.error(
            request, 'Contas de administrador não podem ser excluídas por aqui.'
        )
        return redirect('accounts:profile')

    form = DeleteAccountForm(request.user, request.POST or None)

    if request.method == 'POST':
        # Limite de tentativas: impede testar senhas por esta página.
        if is_rate_limited(request, 'delete-account', limit=5, window=60 * 15):
            form.add_error(None, TOO_MANY_ATTEMPTS)
            return render(
                request, 'accounts/delete.html', {'form': form}, status=429
            )

        if form.is_valid():
            user = request.user
            logout(request)
            user.delete()
            messages.info(request, 'Sua conta foi excluída.')
            return redirect('blog:index')

    return render(request, 'accounts/delete.html', {'form': form})


class AccountPasswordResetView(PasswordResetView):
    """
    "Esqueci minha senha": manda um link por e-mail para criar outra senha.

    Segurança (já embutida no Django): a página de "enviado" aparece igual
    exista ou não uma conta com o e-mail, então ninguém descobre quem tem
    conta por aqui. O link só funciona uma vez e expira (PASSWORD_RESET_TIMEOUT).
    """
    template_name = 'accounts/password_reset_form.html'
    form_class = EmailPasswordResetForm
    email_template_name = 'accounts/emails/password_reset.txt'
    subject_template_name = 'accounts/emails/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        # Assina o e-mail com o nome do blog (Setup), e não com o endereço
        # do site, que no modo público é um "xxxx.trycloudflare.com".
        setup = SiteSetup.objects.order_by('id').first()
        self.extra_email_context = {'site_name': setup.title if setup else 'Blog'}
        return super().form_valid(form)

    def post(self, request, *args, **kwargs):
        # Até 5 pedidos por hora por IP: impede usar o site para lotar a
        # caixa de entrada de alguém com e-mails de redefinição.
        if is_rate_limited(request, 'password-reset', limit=5, window=60 * 60):
            form = self.get_form()
            form.add_error(None, TOO_MANY_ATTEMPTS)
            return self.render_to_response(
                self.get_context_data(form=form), status=429
            )
        return super().post(request, *args, **kwargs)


class AccountPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class AccountPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class AccountPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
