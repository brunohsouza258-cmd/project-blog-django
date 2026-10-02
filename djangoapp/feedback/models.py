from django.db import models


class Feedback(models.Model):
    class Meta:
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedbacks'
        ordering = '-created_at',

    name = models.CharField('Nome', max_length=150)
    email = models.EmailField('E-mail')
    message = models.TextField('Mensagem', max_length=3000)
    created_at = models.DateTimeField('Enviado em', auto_now_add=True)
    # Marque no admin depois de ler, para separar o que já foi visto.
    read = models.BooleanField('Lido', default=False)

    def __str__(self):
        return f'{self.name} ({self.created_at:%d/%m/%Y})'
