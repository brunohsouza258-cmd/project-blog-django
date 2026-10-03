import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image

from blog.models import Category, Post

DATA_FILE = Path(__file__).resolve().parents[2] / 'data' / 'famosos.json'
# O Wikimedia pede que robôs se identifiquem pelo User-Agent.
USER_AGENT = 'BlogDjangoPessoal/1.0 (projeto de estudo)'
# Só baixa imagens do Wikimedia, que é de onde vêm as fotos do JSON.
# Originais ficam em upload.*; versões redimensionadas, em thumb.*.
ALLOWED_HOSTS = {'upload.wikimedia.org', 'thumb.wikimedia.org'}
MAX_DOWNLOAD = 15 * 1024 * 1024


def download_cover(url):
    """Baixa a imagem e devolve um JPEG limpo (sem metadados), ou None."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS:
        return None

    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read(MAX_DOWNLOAD + 1)
            break
        except urllib.error.HTTPError as error:
            if error.code != 429:
                raise
            # 429 = muitas requisições seguidas. O servidor diz quanto tempo
            # esperar no cabeçalho Retry-After; sem ele, espera cada vez mais.
            retry_after = error.headers.get('Retry-After', '')
            wait = int(retry_after) if retry_after.isdigit() else 15 * (attempt + 1)
            time.sleep(min(wait, 120))
        except OSError:
            time.sleep(5 * (attempt + 1))  # rede instável
    else:
        raise OSError('o Wikimedia continuou limitando as requisições')

    if len(data) > MAX_DOWNLOAD:
        return None

    # Abrir com o Pillow confere que é mesmo uma imagem. Salvar de novo como
    # JPEG padroniza o formato e descarta metadados escondidos no arquivo.
    with Image.open(BytesIO(data)) as image:
        return compress_cover(image)


def compress_cover(image):
    """
    Encaixa a imagem numa caixa de 1200x1200 (retratos ficam com 1200 de
    altura) e salva um JPEG leve. Capas abaixo de ~300 KB aparecem com foto
    na prévia do WhatsApp e deixam o site mais rápido no celular.
    """
    image = image.convert('RGB')
    image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, 'JPEG', quality=78, optimize=True, progressive=True)
    return output.getvalue()


class Command(BaseCommand):
    help = (
        'Cria os posts de exemplo sobre famosos (blog/data/famosos.json) e '
        'baixa as capas do Wikimedia Commons. Pode rodar várias vezes: posts '
        'que já existem são ignorados, só ganham a capa se estiverem sem.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--sem-imagens', action='store_true',
            help='Não baixa as capas (útil sem internet e nos testes).',
        )

    def handle(self, *args, **options):
        posts = json.loads(DATA_FILE.read_text(encoding='utf-8'))
        author = (
            get_user_model().objects
            .filter(is_superuser=True).order_by('id').first()
        )
        # As datas são relativas ao dia em que o comando roda: "days"
        # negativo = já publicado; positivo = agendado para o futuro.
        today = timezone.localtime().replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        created = covers = 0

        for item in posts:
            post = Post.objects.filter(title=item['title']).first()

            if post is None:
                category, _ = Category.objects.get_or_create(
                    name=item['category']
                )
                post = Post.objects.create(
                    title=item['title'],
                    excerpt=item['excerpt'],
                    content=item['content'],
                    category=category,
                    is_published=True,
                    published_at=today + timedelta(days=item['days']),
                    created_by=author,
                )
                created += 1

            if options['sem_imagens'] or post.cover or not item.get('cover_url'):
                continue

            try:
                image = download_cover(item['cover_url'])
            except (OSError, ValueError) as error:
                # Uma capa que falha não impede as outras; rode o comando de
                # novo depois para tentar só as que faltaram.
                self.stderr.write(f'Sem capa para "{post.title}": {error}')
                continue
            if image is None:
                self.stderr.write(f'Sem capa para "{post.title}": link fora do Wikimedia.')
                continue

            post.cover_credit = item.get('cover_credit', '')
            post.cover_source = item.get('cover_source', '')
            # save() do ImageField grava o arquivo e chama o Post.save(), que
            # reduz a imagem para no máximo 1200px de largura.
            post.cover.save(f'{post.slug}.jpg', ContentFile(image), save=True)
            covers += 1
            self.stdout.write(f'  capa: {post.title}')
            time.sleep(3)  # educação com o servidor do Wikimedia

        self.stdout.write(self.style.SUCCESS(
            f'{created} posts criados, {len(posts) - created} já existiam, '
            f'{covers} capas baixadas. '
            f'Visíveis no site agora: {Post.objects.published().count()}.'
        ))
