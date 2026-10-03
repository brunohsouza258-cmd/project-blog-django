import uuid

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


def avatar_path(instance, filename):
    # Nome aleatório, nunca o nome do arquivo enviado: evita nomes
    # maliciosos e impede adivinhar a foto de outra pessoa.
    return f'avatars/{uuid.uuid4().hex}.jpg'


class Profile(models.Model):
    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='profile', verbose_name='Usuário',
    )
    avatar = models.ImageField(
        'Foto', upload_to=avatar_path, blank=True, default='',
    )

    @property
    def avatar_url(self):
        # avatar.url dá erro quando não há foto; aqui devolve '' nesse caso,
        # o que é seguro de usar direto nos templates.
        return self.avatar.url if self.avatar else ''

    def __str__(self):
        return f'Perfil de {self.user}'


@receiver(post_delete, sender=Profile)
def delete_avatar_file(sender, instance, **kwargs):
    # Ao excluir a conta (o perfil vai junto), apaga também o arquivo da
    # foto do disco: dado pessoal não fica esquecido no servidor.
    if instance.avatar:
        instance.avatar.delete(save=False)
