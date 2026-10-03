from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm, PasswordResetForm, UserCreationForm,
)
from django.contrib.auth.models import User

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
        email = self.cleaned_data['email'].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Já existe uma conta com este e-mail.')

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']

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
