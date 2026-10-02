from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import Category, Post
from blog.search import search_posts


def make_post(title, **kwargs):
    data = {
        'excerpt': f'Resumo de {title}',
        'content': f'Conteúdo de {title}',
        'is_published': True,
        **kwargs,
    }
    return Post.objects.create(title=title, **data)


class PostModelTests(TestCase):
    def test_slug_is_generated_and_unique(self):
        first = make_post('Meu Primeiro Post!')
        second = make_post('Meu Primeiro Post!')
        self.assertEqual(first.slug, 'meu-primeiro-post')
        self.assertEqual(second.slug, 'meu-primeiro-post-2')

    def test_published_hides_drafts_and_scheduled_posts(self):
        visible = make_post('Publicado')
        make_post('Rascunho', is_published=False)
        make_post('Agendado', published_at=timezone.now() + timedelta(days=1))

        self.assertEqual(list(Post.objects.published()), [visible])

    def test_newest_posts_come_first(self):
        old = make_post('Antigo', published_at=timezone.now() - timedelta(days=2))
        new = make_post('Novo')
        self.assertEqual(list(Post.objects.published()), [new, old])

    def test_reading_time(self):
        post = make_post('Longo', content='palavra ' * 1000)
        self.assertEqual(post.reading_time, 5)
        self.assertEqual(make_post('Curto').reading_time, 1)


class PostPagesTests(TestCase):
    def test_home_lists_new_posts_automatically(self):
        self.assertContains(
            self.client.get(reverse('blog:index')), 'Nenhum post publicado'
        )
        make_post('Post fresquinho')
        self.assertContains(self.client.get(reverse('blog:index')), 'Post fresquinho')

    def test_home_does_not_show_drafts(self):
        make_post('Segredo', is_published=False)
        self.assertNotContains(self.client.get(reverse('blog:index')), 'Segredo')

    def test_pagination(self):
        for i in range(8):
            make_post(f'Post {i}', published_at=timezone.now() - timedelta(hours=i))

        page_2 = self.client.get(reverse('blog:index') + '?page=2')
        self.assertEqual(len(page_2.context['page_obj']), 2)
        # Página inválida não dá erro
        self.assertEqual(self.client.get('/?page=abc').status_code, 200)
        self.assertEqual(self.client.get('/?page=999').status_code, 200)

    def test_post_page(self):
        post = make_post('Aprendendo Django')
        response = self.client.get(post.get_absolute_url())
        self.assertContains(response, 'Aprendendo Django')
        self.assertContains(response, '<title>Aprendendo Django |')

    def test_draft_is_404_for_visitors_but_visible_to_admin(self):
        post = make_post('Rascunho', is_published=False)
        self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)

        admin = User.objects.create_user('admin', password='x', is_staff=True)
        self.client.force_login(admin)
        self.assertContains(self.client.get(post.get_absolute_url()), 'Rascunho:')

    def test_unknown_post_is_404(self):
        response = self.client.get(reverse('blog:post', args=['nao-existe']))
        self.assertEqual(response.status_code, 404)

    def test_post_content_html_is_escaped(self):
        post = make_post('XSS', content='<script>alert(1)</script>')
        response = self.client.get(post.get_absolute_url())
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_category_page(self):
        python = Category.objects.create(name='Python')
        make_post('Sobre Python', category=python)
        make_post('Sobre Docker')

        response = self.client.get(python.get_absolute_url())
        self.assertContains(response, 'Sobre Python')
        self.assertNotContains(response, 'Sobre Docker')

    def test_rss_feed(self):
        make_post('Post no feed')
        make_post('Rascunho fora do feed', is_published=False)
        response = self.client.get(reverse('blog:feed'))
        self.assertContains(response, 'Post no feed')
        self.assertNotContains(response, 'Rascunho fora do feed')


class SearchTests(TestCase):
    def setUp(self):
        self.docker = make_post(
            'Como usar Docker', content='Containers facilitam o deploy.'
        )
        self.django = make_post(
            'Introdução ao Django', content='Programação web com Python.'
        )

    def test_search_finds_by_title_and_content(self):
        self.assertEqual(list(search_posts('docker')), [self.docker])
        self.assertEqual(list(search_posts('containers')), [self.docker])

    def test_search_understands_word_variations(self):
        # "programar" acha "Programação" (radical em português)
        self.assertIn(self.django, search_posts('programação'))

    def test_search_ignores_drafts(self):
        make_post('Docker secreto', is_published=False)
        self.assertEqual(list(search_posts('docker')), [self.docker])

    def test_search_page_and_empty_results(self):
        response = self.client.get(reverse('blog:index') + '?q=docker')
        self.assertContains(response, 'Como usar Docker')
        self.assertNotContains(response, 'Introdução ao Django')

        response = self.client.get(reverse('blog:index') + '?q=xyzabc')
        self.assertContains(response, 'Nenhum post encontrado')

    def test_weird_search_input_does_not_break(self):
        for q in ('', '   ', '!!!', "'; DROP TABLE x;--", 'a' * 500, '& | !'):
            response = self.client.get(reverse('blog:index'), {'q': q})
            self.assertEqual(response.status_code, 200, q)


class PostAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin', 'a@a.com', 'x')
        self.client.force_login(self.admin)

    def test_admin_pages_load(self):
        post = make_post('No admin')
        for url in (
            reverse('admin:blog_post_changelist'),
            reverse('admin:blog_post_add'),
            reverse('admin:blog_post_change', args=[post.pk]),
            reverse('admin:blog_category_add'),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_create_post_from_admin_sets_author(self):
        response = self.client.post(reverse('admin:blog_post_add'), {
            'title': 'Pelo admin',
            'slug': '',
            'excerpt': 'Resumo',
            'content': 'Texto',
            'is_published': 'on',
            'published_at_0': timezone.localtime().strftime('%d/%m/%Y'),
            'published_at_1': '00:00:00',
        })
        self.assertEqual(response.status_code, 302)
        post = Post.objects.get()
        self.assertEqual(post.created_by, self.admin)
        self.assertEqual(post.slug, 'pelo-admin')
        self.assertContains(self.client.get(reverse('blog:index')), 'Pelo admin')


class SeedPostsCommandTests(TestCase):
    def test_creates_posts_once(self):
        from io import StringIO

        from django.core.management import call_command

        call_command('seed_posts', '--sem-imagens', stdout=StringIO())
        self.assertEqual(Post.objects.count(), 15)
        self.assertEqual(Post.objects.published().count(), 12)
        self.assertEqual(Category.objects.count(), 5)

        # Rodar de novo não duplica nada
        output = StringIO()
        call_command('seed_posts', '--sem-imagens', stdout=output)
        self.assertEqual(Post.objects.count(), 15)
        self.assertIn('0 posts criados, 15 já existiam, 0 capas', output.getvalue())


class HeaderAndCoverTests(TestCase):
    def test_logged_user_name_and_initial_in_header(self):
        user = User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'x', first_name='Maria'
        )
        self.client.force_login(user)
        response = self.client.get(reverse('blog:index'))
        # Chip do celular + saudação do computador
        self.assertContains(response, 'class="user-chip"')
        self.assertContains(response, '<span class="user-name">Maria</span>')
        self.assertContains(response, 'Olá, <strong>Maria</strong>')
        self.assertContains(response, '>M</span>')

    def test_visitor_does_not_see_user_chip(self):
        response = self.client.get(reverse('blog:index'))
        self.assertNotContains(response, 'class="user-chip"')

    def test_cover_credit_is_shown_with_link(self):
        post = make_post(
            'Com capa', cover='posts/teste.jpg',
            cover_credit='Foto: Fulano (CC BY-SA 4.0), via Wikimedia Commons',
            cover_source='https://commons.wikimedia.org/wiki/File:Teste.jpg',
        )
        response = self.client.get(post.get_absolute_url())
        self.assertContains(response, 'Foto: Fulano (CC BY-SA 4.0)')
        self.assertContains(
            response, 'href="https://commons.wikimedia.org/wiki/File:Teste.jpg"'
        )
