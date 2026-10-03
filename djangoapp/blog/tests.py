from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import Category, Comment, Post
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
        self.assertEqual(Post.objects.count(), 27)
        self.assertEqual(Post.objects.published().count(), 24)
        self.assertEqual(Category.objects.count(), 6)

        # Rodar de novo não duplica nada
        output = StringIO()
        call_command('seed_posts', '--sem-imagens', stdout=output)
        self.assertEqual(Post.objects.count(), 27)
        self.assertIn('0 posts criados, 27 já existiam, 0 capas', output.getvalue())


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

    def test_header_shows_only_first_name(self):
        user = User.objects.create_user(
            'mc@email.com', 'mc@email.com', 'x', first_name='Maria Clara Souza'
        )
        self.client.force_login(user)
        response = self.client.get(reverse('blog:index'))
        self.assertContains(response, '<span class="user-name">Maria</span>')
        self.assertNotContains(response, 'Clara')

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


class CommentTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.post = make_post('Post comentável')
        self.maria = User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'x', first_name='Maria Clara'
        )
        self.joao = User.objects.create_user(
            'joao@email.com', 'joao@email.com', 'x', first_name='João'
        )
        self.url = reverse('blog:comment_create', args=[self.post.slug])

    def comment(self, text='Muito bom!', user=None):
        self.client.force_login(user or self.maria)
        return self.client.post(self.url, {'text': text})

    def test_visitor_cannot_comment(self):
        response = self.client.post(self.url, {'text': 'oi'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)
        self.assertFalse(Comment.objects.exists())

    def test_visitor_sees_invitation_to_login(self):
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, 'para comentar')

    def test_comment_is_published_with_first_name_only(self):
        response = self.comment()
        self.assertRedirects(
            response, f'{self.post.get_absolute_url()}#comentarios',
            fetch_redirect_response=False,
        )
        page = self.client.get(self.post.get_absolute_url())
        self.assertContains(page, 'Muito bom!')
        self.assertContains(page, '<strong>Maria</strong>')
        # O e-mail de quem comenta nunca aparece na página
        self.client.logout()
        page = self.client.get(self.post.get_absolute_url())
        self.assertNotContains(page, 'maria@email.com')

    def test_empty_and_too_long_comments_are_rejected(self):
        self.comment('   ')
        self.comment('a' * 1001)
        self.assertFalse(Comment.objects.exists())

    def test_comment_html_is_escaped(self):
        self.comment('<script>alert(1)</script>')
        page = self.client.get(self.post.get_absolute_url())
        self.assertNotContains(page, '<script>alert(1)</script>')
        self.assertContains(page, '&lt;script&gt;')

    def test_cannot_comment_on_draft(self):
        draft = make_post('Rascunho', is_published=False)
        self.client.force_login(self.maria)
        response = self.client.post(
            reverse('blog:comment_create', args=[draft.slug]), {'text': 'oi'}
        )
        self.assertEqual(response.status_code, 404)

    def test_get_is_not_allowed(self):
        self.client.force_login(self.maria)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_delete_own_comment_only(self):
        self.comment()
        comment = Comment.objects.get()
        delete_url = reverse('blog:comment_delete', args=[comment.pk])

        self.client.force_login(self.joao)
        self.client.post(delete_url)
        self.assertTrue(Comment.objects.exists())

        self.client.force_login(self.maria)
        self.client.post(delete_url)
        self.assertFalse(Comment.objects.exists())

    def test_admin_can_delete_any_comment(self):
        self.comment()
        admin = User.objects.create_user('adm', password='x', is_staff=True)
        self.client.force_login(admin)
        self.client.post(reverse('blog:comment_delete', args=[Comment.objects.get().pk]))
        self.assertFalse(Comment.objects.exists())

    def test_hidden_comment_is_not_shown(self):
        self.comment('Comentário escondido')
        Comment.objects.update(is_visible=False)
        page = self.client.get(self.post.get_absolute_url())
        self.assertNotContains(page, 'Comentário escondido')

    def test_comment_rate_limit(self):
        for i in range(10):
            self.comment(f'comentário {i}')
        self.comment('um a mais')
        self.assertEqual(Comment.objects.count(), 10)

    def test_comments_are_deleted_with_account(self):
        self.comment()
        self.maria.delete()
        self.assertFalse(Comment.objects.exists())


class TempoAtrasTests(TestCase):
    def test_tempo_atras(self):
        from datetime import timedelta

        from blog.templatetags.blog_extras import tempo_atras
        now = timezone.now()
        self.assertEqual(tempo_atras(now - timedelta(seconds=10)), 'agora')
        self.assertEqual(tempo_atras(now - timedelta(minutes=3, seconds=5)), 'há 3\xa0minutos')
        self.assertEqual(tempo_atras(now - timedelta(hours=2, minutes=5)), 'há 2\xa0horas')
