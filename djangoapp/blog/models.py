from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from utils.images import resize_image
from utils.model_validators import validate_cover_image


def unique_slug(instance, value, max_length=255):
    """
    Gera um slug (texto da URL) único a partir do título.
    Ex.: "Meu Primeiro Post!" -> "meu-primeiro-post"; se já existir,
    vira "meu-primeiro-post-2", "meu-primeiro-post-3"...
    """
    base = slugify(value)[:max_length - 5] or 'post'
    slug = base
    number = 2
    queryset = type(instance).objects.exclude(pk=instance.pk)

    while queryset.filter(slug=slug).exists():
        slug = f'{base}-{number}'
        number += 1

    return slug


class Category(models.Model):
    class Meta:
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'
        ordering = 'name',

    name = models.CharField('Nome', max_length=60, unique=True)
    slug = models.SlugField(
        unique=True, max_length=80, blank=True,
        help_text='Deixe em branco para gerar a partir do nome.',
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, 80)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('blog:category', args=[self.slug])

    def __str__(self):
        return self.name


class PostQuerySet(models.QuerySet):
    def published(self):
        # Só aparece no site o que está publicado E com data que já chegou.
        # Assim dá para agendar um post: ele surge sozinho na data marcada.
        return self.filter(
            is_published=True, published_at__lte=timezone.now()
        ).select_related('category')


class Post(models.Model):
    class Meta:
        verbose_name = 'Post'
        verbose_name_plural = 'Posts'
        ordering = '-published_at', '-id',

    title = models.CharField('Título', max_length=120)
    slug = models.SlugField(
        unique=True, max_length=255, blank=True,
        help_text='Parte da URL. Deixe em branco para gerar a partir do título.',
    )
    excerpt = models.CharField(
        'Resumo', max_length=255,
        help_text='Aparece no card da página inicial e ajuda a IA a '
                  'entender o post.',
    )
    content = models.TextField(
        'Conteúdo',
        help_text='Texto do post. Deixe uma linha em branco entre parágrafos.',
    )
    cover = models.ImageField(
        'Capa', upload_to='posts/%Y/%m/', blank=True, default='',
        validators=[validate_cover_image],
        help_text='JPG, PNG ou WEBP. Imagens grandes são reduzidas para 1200px.',
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Categoria', related_name='posts',
    )
    is_published = models.BooleanField(
        'Publicado', default=False,
        help_text='Desmarcado, o post fica como rascunho e só você vê.',
    )
    published_at = models.DateTimeField(
        'Data de publicação', default=timezone.now,
        help_text='Use uma data futura para agendar a publicação.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, editable=False, related_name='posts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.title)

        # Mesmo esquema do favicon: só redimensiona quando a capa mudou.
        current_cover_name = str(self.cover.name)
        super().save(*args, **kwargs)

        if self.cover and current_cover_name != self.cover.name:
            resize_image(self.cover, 1200, quality=80)

    @property
    def reading_time(self):
        # Média de 200 palavras por minuto.
        words = len(self.content.split())
        return max(1, round(words / 200))

    def get_absolute_url(self):
        return reverse('blog:post', args=[self.slug])

    def __str__(self):
        return self.title
