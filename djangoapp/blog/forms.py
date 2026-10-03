from django import forms

from blog.models import Comment


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = 'text',
        labels = {'text': 'Seu comentário'}
        widgets = {
            'text': forms.Textarea(attrs={
                'rows': 3,
                'maxlength': 1000,
                'placeholder': 'Escreva o que achou do post...',
            }),
        }

    def clean_text(self):
        text = self.cleaned_data['text'].strip()
        if not text:
            raise forms.ValidationError('Escreva alguma coisa.')
        return text
