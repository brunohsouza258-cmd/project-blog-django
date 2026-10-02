import json
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from blog.models import Category, Post

DATA_FILE = Path(__file__).resolve().parents[2] / 'data' / 'famosos.json'


class Command(BaseCommand):
    help = (
        'Cria os posts de exemplo sobre famosos (blog/data/famosos.json). '
        'Pode rodar várias vezes: posts que já existem são ignorados.'
    )

    @transaction.atomic
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
        created = 0

        for item in posts:
            if Post.objects.filter(title=item['title']).exists():
                continue

            category, _ = Category.objects.get_or_create(name=item['category'])
            Post.objects.create(
                title=item['title'],
                excerpt=item['excerpt'],
                content=item['content'],
                category=category,
                is_published=True,
                published_at=today + timedelta(days=item['days']),
                created_by=author,
            )
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f'{created} posts criados, {len(posts) - created} já existiam. '
            f'Visíveis no site agora: {Post.objects.published().count()}.'
        ))
