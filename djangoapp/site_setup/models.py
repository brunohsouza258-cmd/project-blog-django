from django.db import models
from utils.images import resize_image
from utils.model_validators import validate_png
from utils.validators import validate_safe_url


class MenuLink(models.Model):
    class Meta:
        verbose_name = 'Menu Link'
        verbose_name_plural = 'Menu Links'

    text = models.CharField(max_length=50)
    url_or_path = models.CharField(
        max_length=2048, validators=[validate_safe_url]
    )
    new_tab = models.BooleanField(default=False)
    site_setup = models.ForeignKey(
        'SiteSetup', on_delete=models.CASCADE, blank=True, null=True,
        default=None
    )

    def __str__(self):
        return self.text

class SiteSetup(models.Model):
    class Meta:
        verbose_name = 'Setup'
        verbose_name_plural = 'Setup'

    title = models.CharField(max_length=65)
    description = models.CharField(max_length=255)

    show_header = models.BooleanField(default=True)
    show_search = models.BooleanField(default=True)
    show_menu = models.BooleanField(default=True)
    show_description = models.BooleanField(default=True)
    show_pagination = models.BooleanField(default=True)
    show_footer = models.BooleanField(default=True)

    favicon = models.ImageField(
        upload_to='assets/favicon/%Y/%m',
        blank=True, default='',
        validators=[validate_png]
    )

    def save(self, *args, **kwargs):
        # Guarda o nome do favicon ANTES de salvar. Num upload novo ele é só
        # o nome do arquivo enviado (ex.: "logo.png"); depois do save o Django
        # move o arquivo e o nome vira o caminho completo
        # (ex.: "assets/favicon/2026/10/logo.png"). Se o nome mudou, é porque
        # chegou um arquivo novo.
        current_favicon_name = str(self.favicon.name)
        super().save(*args, **kwargs)
        favicon_changed = False

        if self.favicon:
            favicon_changed = current_favicon_name != self.favicon.name

        # Só redimensiona quando o favicon foi trocado, para não reprocessar
        # a imagem toda vez que alguém salvar o Setup no admin.
        if favicon_changed:
            resize_image(self.favicon, 32)

    def __str__(self):
        return self.title    