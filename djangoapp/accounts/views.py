from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordChangeView, PasswordResetCompleteView,
    PasswordResetConfirmView, PasswordResetDoneView, PasswordResetView,
)
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods, require_POST

from accounts.context_processors import WELCOME_SESSION_KEY
from accounts.forms import (
    AvatarForm, DeleteAccountForm, EmailAuthenticationForm,
    EmailPasswordResetForm, ProfileForm, RegisterForm, ResendConfirmationForm,
)
from accounts.models import Profile
from accounts.tokens import make_confirmation_token, read_confirmation_token
from site_setup.models import SiteSetup
from utils.rate_limit import is_rate_limited

TOO_MANY_ATTEMPTS = 'Muitas tentativas seguidas. Espere alguns minutos.'


def _site_name():
    setup = SiteSetup.objects.order_by('id').first()
    return setup.title if setup else 'Blog'


def _send_confirmation_email(request, user):
    link = request.build_absolute_uri(
        reverse('accounts:confirm_email', args=[make_confirmation_token(user)])
    )
    context = {'user': user, 'link': link, 'site_name': _site_name()}
    send_mail(
        subject=render_to_string(
            'accounts/emails/confirm_email_subject.txt', context
        ).strip(),
        message=render_to_string('accounts/emails/confirm_email.txt', context),
        from_email=None,  # usa o DEFAULT_FROM_EMAIL do settings.py
        recipient_list=[user.email],
        fail_silently=True,
    )


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
        email = form.cleaned_data['email']
        existing = User.objects.filter(email__iexact=email).first()

        if existing and existing.is_active:
            # Já existe conta de verdade: avisa por e-mail (nunca pela
            # resposta do site) e não cria nada. Quem não tem acesso a essa
            # caixa de entrada não aprende nada com isto.
            send_mail(
                subject=f'[Blog] Tentativa de cadastro com seu e-mail - {_site_name()}',
                message=(
                    'Alguém tentou criar uma conta neste blog usando o seu '
                    'e-mail, mas você já tem uma conta por aqui.\n\n'
                    'Se foi você, é só entrar normalmente. Esqueceu a '
                    f'senha? {request.build_absolute_uri(reverse("accounts:password_reset"))}\n\n'
                    'Se não foi você, pode ignorar este e-mail: nada muda '
                    'na sua conta.'
                ),
                from_email=None,
                recipient_list=[email],
                fail_silently=True,
            )
        elif existing:
            # Cadastro anterior nunca confirmado: atualiza com os dados
            # desta tentativa (pode ter sido um erro de senha) e manda um
            # novo link, em vez de dizer "e-mail já cadastrado".
            existing.first_name = form.cleaned_data['first_name']
            existing.set_password(form.cleaned_data['password1'])
            existing.save()
            _send_confirmation_email(request, existing)
        else:
            user = form.save()
            _send_confirmation_email(request, user)

        # Mesma página nos três casos: nada na resposta do site revela se
        # o e-mail já tinha conta.
        return render(request, 'accounts/register_done.html', {'email': email})

    return render(request, 'accounts/register.html', {'form': form})


def confirm_email(request, token):
    """Ativa a conta quando a pessoa abre o link recebido por e-mail."""
    user_pk = read_confirmation_token(token)
    user = (
        User.objects.filter(pk=user_pk, is_active=False).first()
        if user_pk is not None else None
    )

    if user is None:
        # Link forjado, expirado (3 dias) ou já usado: uma vez confirmada,
        # a conta fica com is_active=True e o mesmo link para de funcionar,
        # então ele não serve como "link mágico" reutilizável de login.
        return render(request, 'accounts/confirm_email_invalid.html', status=400)

    user.is_active = True
    user.save(update_fields=['is_active'])
    login(request, user)

    # Só agora, com a conta confirmada de verdade, avisa o dono do blog.
    send_mail(
        subject=f'[Blog] Nova conta: {user.first_name}',
        message=f'Nome: {user.first_name}\nE-mail: {user.email}',
        from_email=None,
        recipient_list=[settings.SIGNUP_NOTIFY_EMAIL],
        fail_silently=True,
    )

    # Mostra o "Seja bem-vindo" no meio da tela na próxima página.
    request.session[WELCOME_SESSION_KEY] = True
    return redirect('blog:index')


def resend_confirmation(request):
    """"Não recebi o e-mail" — reenvia o link de confirmação."""
    form = ResendConfirmationForm(request.POST or None)

    if request.method == 'POST' and is_rate_limited(
        request, 'resend-confirmation', limit=5, window=60 * 60
    ):
        form.add_error(None, TOO_MANY_ATTEMPTS)
        return render(
            request, 'accounts/resend_confirmation.html', {'form': form},
            status=429,
        )

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        user = User.objects.filter(email__iexact=email, is_active=False).first()
        if user:
            _send_confirmation_email(request, user)
        # Mesma página exista ou não um cadastro pendente com esse e-mail.
        return render(request, 'accounts/register_done.html', {'email': email})

    return render(request, 'accounts/resend_confirmation.html', {'form': form})


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
        # super() faz o login (e troca a sessão por segurança); só depois
        # marcamos o "Seja bem-vindo", senão a marca se perderia na troca.
        response = super().form_valid(form)
        self.request.session[WELCOME_SESSION_KEY] = True
        return response


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

    return render(request, 'accounts/profile.html', {
        'form': form,
        'avatar_form': AvatarForm(),
    })


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


@login_required
@require_POST
def avatar_update(request):
    """Envia, troca ou remove a foto de perfil."""
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if 'remove' in request.POST:
        if profile.avatar:
            profile.avatar.delete(save=True)  # apaga o arquivo também
            messages.info(request, 'Foto removida.')
        return redirect('accounts:profile')

    # Até 10 envios por hora: processar imagem gasta CPU do servidor.
    if is_rate_limited(request, f'avatar:{request.user.pk}', 10, 60 * 60):
        messages.error(request, TOO_MANY_ATTEMPTS)
        return redirect('accounts:profile')

    form = AvatarForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, form.errors['avatar'][0])
        return redirect('accounts:profile')

    new_avatar = form.processed_avatar()
    if profile.avatar:
        profile.avatar.delete(save=False)  # não deixa a foto antiga no disco
    profile.avatar.save(new_avatar.name, new_avatar, save=True)
    messages.success(request, 'Foto atualizada.')
    return redirect('accounts:profile')
