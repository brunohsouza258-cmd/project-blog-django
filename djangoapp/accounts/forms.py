from io import BytesIO

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm, PasswordResetForm, UserCreationForm,
)
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from utils.validators import validate_single_line


class RegisterForm(UserCreationForm):
    # O UserCreationForm já cuida da senha: confere se as duas são iguais e
    # aplica os validadores do AUTH_PASSWORD_VALIDATORS do settings.py.
    first_name = forms.CharField(
        label='Nome',
        max_length=150,
        validators=[validate_single_line],
        widget=forms.TextInput(attrs={
            'placeholder': 'Seu nome',
            'autocomplete': 'given-name',
        }),
    )
    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={
            'placeholder': 'voce@email.com',
            'autocomplete': 'email',
        }),
    )

    class Meta:
        model = User
        # O "username" não aparece no formulário: usamos o próprio e-mail
        # como username (veja o save abaixo).
        fields = 'first_name', 'email',

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['placeholder'] = 'Crie uma senha'
        self.fields['password2'].widget.attrs['placeholder'] = 'Repita a senha'

    def clean_email(self):
        # Salva sempre em minúsculas para "Fulano@Gmail.com" e
        # "fulano@gmail.com" não virarem duas contas diferentes.
        #
        # Propositalmente NÃO recusamos aqui um e-mail que já tem conta: um
        # erro "já existe uma conta com este e-mail" no formulário permite a
        # qualquer visitante descobrir quem tem conta no blog, só testando
        # e-mails (enumeração de contas). A view decide o que fazer com um
        # e-mail repetido e responde sempre a mesma coisa nos dois casos.
        return self.cleaned_data['email'].strip().lower()

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        # Conta começa desativada: só entra em vigor quando o link do
        # e-mail de confirmação é aberto (veja accounts/views.py).
        user.is_active = False

        if commit:
            user.save()

        return user


class EmailAuthenticationForm(AuthenticationForm):
    # O formulário de login do Django chama o campo de "username". Como o
    # username é o e-mail, só trocamos o rótulo e o tipo do campo.
    username = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={
            'placeholder': 'voce@email.com',
            'autocomplete': 'email',
            'autofocus': True,
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password'].widget.attrs['placeholder'] = 'Sua senha'

    def clean_username(self):
        return self.cleaned_data['username'].strip().lower()

    def confirm_login_allowed(self, user):
        # Django já bloqueia usuário inativo aqui; só trocamos a mensagem
        # padrão em inglês por uma em português explicando o motivo. O link
        # para reenviar a confirmação fica no template (login.html), não
        # nesta mensagem: assim não precisamos marcar HTML como seguro.
        if not user.is_active:
            raise forms.ValidationError(
                'Confirme seu e-mail antes de entrar. Veja o link abaixo '
                'para reenviar a confirmação.',
                code='inactive',
            )
        super().confirm_login_allowed(user)


class ProfileForm(forms.ModelForm):
    """Edição dos dados da conta na página "Minha conta"."""

    class Meta:
        model = User
        fields = 'first_name', 'email',
        labels = {'first_name': 'Nome', 'email': 'E-mail'}
        widgets = {
            'first_name': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No model do Django esses campos são opcionais; aqui são obrigatórios.
        self.fields['first_name'].required = True
        self.fields['first_name'].validators.append(validate_single_line)
        self.fields['email'].required = True

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        # O próprio usuário pode manter o e-mail; outro usuário, não.
        taken = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError('Já existe uma conta com este e-mail.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # O login é feito pelo e-mail, que fica guardado no username.
        user.username = user.email
        if commit:
            user.save()
        return user


class DeleteAccountForm(forms.Form):
    """Confirma a senha antes de excluir a conta (ação sem volta)."""

    password = forms.CharField(
        label='Sua senha',
        strip=False,
        widget=forms.PasswordInput(attrs={
            'autocomplete': 'current-password',
            'placeholder': 'Digite sua senha para confirmar',
        }),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.user.check_password(password):
            raise forms.ValidationError('Senha incorreta.')
        return password


class EmailPasswordResetForm(PasswordResetForm):
    # Mesmo rótulo e exemplo dos outros formulários do site.
    email = forms.EmailField(
        label='E-mail',
        max_length=254,
        widget=forms.EmailInput(attrs={
            'placeholder': 'voce@email.com',
            'autocomplete': 'email',
            'autofocus': True,
        }),
    )


class ResendConfirmationForm(forms.Form):
    """"Não recebi o e-mail de confirmação" — pede o e-mail de novo."""

    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={
            'placeholder': 'voce@email.com',
            'autocomplete': 'email',
            'autofocus': True,
        }),
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


AVATAR_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
AVATAR_MAX_PIXELS = 25_000_000      # ~5000x5000
AVATAR_SIZE = 256                   # foto final: 256x256
AVATAR_FORMATS = {'JPEG', 'PNG', 'WEBP'}


class AvatarForm(forms.Form):
    avatar = forms.ImageField(
        label='Foto de perfil',
        help_text='PNG, JPG ou WEBP, até 2 MB.',
        widget=forms.ClearableFileInput(attrs={
            'accept': 'image/png,image/jpeg,image/webp',
        }),
    )

    def clean_avatar(self):
        """
        O ImageField do Django já abre o arquivo com o Pillow e recusa o que
        não for imagem (ex.: um .exe renomeado para .png). Aqui somamos as
        regras do site: tamanho, formato e dimensão.
        """
        upload = self.cleaned_data['avatar']

        if upload.size > AVATAR_MAX_BYTES:
            raise forms.ValidationError('A foto pode ter no máximo 2 MB.')

        # O Django guarda a imagem aberta (só o cabeçalho) em upload.image
        image = upload.image
        if image.format not in AVATAR_FORMATS:
            raise forms.ValidationError('Use uma imagem PNG, JPG ou WEBP.')

        # "Bomba de imagem": arquivo pequeno que vira uma imagem gigantesca
        # na memória ao abrir. Recusamos antes de carregar os pixels.
        width, height = image.size
        if width * height > AVATAR_MAX_PIXELS:
            raise forms.ValidationError('Imagem grande demais (em pixels).')

        return upload

    def processed_avatar(self):
        """
        Gera a foto final: quadrada, 256x256, JPEG novo. Recriar o arquivo do
        zero descarta tudo que não é a imagem em si, inclusive os metadados
        EXIF, que em fotos de celular incluem a localização GPS de onde a foto
        foi tirada.
        """
        upload = self.cleaned_data['avatar']
        upload.seek(0)
        with Image.open(upload) as image:
            # Fotos de celular guardam a rotação no EXIF; aplica antes de
            # descartar os metadados, senão a foto ficaria deitada.
            image = ImageOps.exif_transpose(image)
            image = image.convert('RGB')
            # Corta no centro para ficar quadrada, sem distorcer o rosto.
            image = ImageOps.fit(
                image, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS
            )
            output = BytesIO()
            image.save(output, 'JPEG', quality=85, optimize=True)
        return ContentFile(output.getvalue(), name='avatar.jpg')
