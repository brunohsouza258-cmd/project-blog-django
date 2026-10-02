from django import forms
from feedback.models import Feedback
from utils.validators import validate_single_line


class FeedbackForm(forms.ModelForm):
    # Armadilha para robôs (honeypot): o campo fica escondido pelo CSS, então
    # uma pessoa nunca preenche. Robôs de spam preenchem todos os campos.
    website = forms.CharField(required=False)

    class Meta:
        model = Feedback
        fields = 'name', 'email', 'message',
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Seu nome'}),
            'email': forms.EmailInput(attrs={'placeholder': 'voce@email.com'}),
            'message': forms.Textarea(attrs={
                'placeholder': 'Conte o que achou, sugestões, problemas...',
                'rows': 6,
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].validators.append(validate_single_line)

    def is_spam(self):
        return bool(self.cleaned_data.get('website'))
