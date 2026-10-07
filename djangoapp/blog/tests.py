from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import Category, Comment, Like, Post
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


class OpenGraphTests(TestCase):
    def test_post_page_has_preview_tags_with_absolute_image(self):
        post = make_post('Com prévia', cover='posts/capa.jpg')
        response = self.client.get(post.get_absolute_url())
        self.assertContains(response, '<meta property="og:title" content="Com prévia">')
        self.assertContains(
            response, '<meta property="og:description" content="Resumo de Com prévia">'
        )
        self.assertContains(response, 'content="http://testserver/media/posts/capa.jpg"')
        self.assertContains(response, '<meta property="og:type" content="article">')

    def test_home_has_site_preview(self):
        response = self.client.get(reverse('blog:index'))
        self.assertContains(response, '<meta property="og:type" content="website">')


class TempoAtrasTests(TestCase):
    def test_tempo_atras(self):
        from datetime import timedelta

        from blog.templatetags.blog_extras import tempo_atras
        now = timezone.now()
        self.assertEqual(tempo_atras(now - timedelta(seconds=10)), 'agora')
        self.assertEqual(tempo_atras(now - timedelta(minutes=3, seconds=5)), 'há 3\xa0minutos')
        self.assertEqual(tempo_atras(now - timedelta(hours=2, minutes=5)), 'há 2\xa0horas')


class FaviconTests(TestCase):
    def test_default_icons_in_head(self):
        response = self.client.get(reverse('blog:index'))
        self.assertContains(response, 'blog/img/favicon.svg')
        self.assertContains(response, 'blog/img/apple-touch-icon.png')
        self.assertContains(response, '<meta name="theme-color" content="#12070f">')

    def test_favicon_ico_redirects_to_static_file(self):
        response = self.client.get('/favicon.ico')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith('blog/img/favicon.ico'))


class SelfHostedFontsTests(TestCase):
    def test_no_google_fonts_and_local_fonts_preloaded(self):
        response = self.client.get(reverse('blog:index'))
        self.assertNotContains(response, 'fonts.googleapis.com')
        self.assertNotContains(response, 'fonts.gstatic.com')
        self.assertContains(response, 'blog/fonts/inter-400.woff2')
        csp = response['Content-Security-Policy-Report-Only']
        self.assertIn("font-src 'self'", csp)
        self.assertNotIn('google', csp)


class SeoTests(TestCase):
    def test_sitemap_lists_only_published_posts(self):
        cat = Category.objects.create(name='Esporte')
        make_post('Publicado', category=cat)
        make_post('Rascunho', is_published=False)
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/post/publicado/')
        self.assertContains(response, '/categoria/esporte/')
        self.assertNotContains(response, 'rascunho')
        self.assertContains(response, '<lastmod>')

    def test_robots_txt_points_to_sitemap_and_hides_admin(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertContains(response, 'Sitemap: http://testserver/sitemap.xml')
        self.assertContains(response, 'Disallow: /conta/')
        self.assertNotContains(response, 'admin')

    def test_canonical_and_noindex(self):
        for i in range(8):
            make_post(f'Post {i}')
        home = self.client.get('/?utm_source=whatsapp')
        self.assertContains(home, '<link rel="canonical" href="http://testserver/">')
        self.assertNotContains(home, 'noindex')
        page2 = self.client.get('/?page=2')
        self.assertContains(page2, 'href="http://testserver/?page=2"')
        self.assertContains(self.client.get('/?q=post'), '<meta name="robots" content="noindex">')
        self.assertContains(self.client.get('/conta/entrar/'), '<meta name="robots" content="noindex">')


class PrivacyPolicyTests(TestCase):
    def test_page_and_links(self):
        response = self.client.get(reverse('blog:privacy'))
        self.assertContains(response, 'Política de')
        self.assertContains(response, 'LGPD')
        self.assertContains(response, 'Bruno.h.souza258@gmail.com')
        privacy_url = reverse('blog:privacy')
        # Link no rodapé de todas as páginas, no cadastro e no feedback
        for url in ('/', reverse('accounts:register'), reverse('feedback:feedback')):
            self.assertContains(self.client.get(url), f'href="{privacy_url}"', msg_prefix=url)
        self.assertContains(self.client.get('/sitemap.xml'), privacy_url)


def png_bytes(size=(1600, 2400)):
    from io import BytesIO

    from PIL import Image
    buffer = BytesIO()
    Image.new('RGB', size, (236, 72, 153)).save(buffer, 'PNG')
    return buffer.getvalue()


class SeedCoverDownloadTests(TestCase):
    """Download das capas do seed_posts, com a internet simulada."""

    def fake_urlopen(self, data):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.read.return_value = data
        return response

    def test_only_https_wikimedia_is_downloaded(self):
        from unittest.mock import patch

        from blog.management.commands.seed_posts import download_cover
        with patch('urllib.request.urlopen') as urlopen:
            for url in ('https://evil.com/x.jpg', 'http://upload.wikimedia.org/x.jpg',
                        'https://upload.wikimedia.org.evil.com/x.jpg', 'file:///etc/passwd'):
                self.assertIsNone(download_cover(url), url)
            urlopen.assert_not_called()

    def test_download_becomes_light_jpeg_inside_1200_box(self):
        from io import BytesIO
        from unittest.mock import patch

        from PIL import Image

        from blog.management.commands.seed_posts import download_cover
        with patch('urllib.request.urlopen', return_value=self.fake_urlopen(png_bytes())):
            data = download_cover('https://thumb.wikimedia.org/foto.png')
        with Image.open(BytesIO(data)) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.size, (800, 1200))

    def test_too_many_requests_waits_and_retries(self):
        import urllib.error
        from email.message import Message
        from unittest.mock import patch

        from blog.management.commands.seed_posts import download_cover
        headers = Message()
        headers['Retry-After'] = '7'
        busy = urllib.error.HTTPError('u', 429, 'Too Many', headers, None)
        with patch('urllib.request.urlopen', side_effect=[busy, self.fake_urlopen(png_bytes((50, 50)))]), \
                patch('time.sleep') as sleep:
            self.assertIsNotNone(download_cover('https://upload.wikimedia.org/a.png'))
        sleep.assert_called_once_with(7)

    def test_huge_download_is_refused(self):
        from unittest.mock import patch

        from blog.management.commands.seed_posts import MAX_DOWNLOAD, download_cover
        with patch('urllib.request.urlopen', return_value=self.fake_urlopen(b'x' * (MAX_DOWNLOAD + 1))):
            self.assertIsNone(download_cover('https://upload.wikimedia.org/a.png'))

    def test_command_sets_cover_and_credit_and_survives_failures(self):
        import shutil
        import tempfile
        from io import StringIO
        from pathlib import Path
        from unittest.mock import patch

        from django.core.management import call_command
        from django.test import override_settings

        media = tempfile.mkdtemp()
        calls = {'n': 0}

        def fake_download(url):
            calls['n'] += 1
            if calls['n'] == 2:
                raise OSError('falha de rede simulada')
            from blog.management.commands.seed_posts import compress_cover
            from io import BytesIO
            from PIL import Image
            with Image.open(BytesIO(png_bytes((300, 200)))) as image:
                return compress_cover(image)

        try:
            with override_settings(MEDIA_ROOT=Path(media)), \
                    patch('blog.management.commands.seed_posts.download_cover', side_effect=fake_download), \
                    patch('time.sleep'):
                err = StringIO()
                call_command('seed_posts', stdout=StringIO(), stderr=err)
            with_cover = Post.objects.exclude(cover='')
            self.assertEqual(with_cover.count(), Post.objects.count() - 1)
            self.assertIn('Wikimedia Commons', with_cover.first().cover_credit)
            self.assertIn('falha de rede simulada', err.getvalue())
        finally:
            shutil.rmtree(media, ignore_errors=True)


class LikeTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.post = make_post('Post curtível')
        self.maria = User.objects.create_user(
            'maria@email.com', 'maria@email.com', 'x', first_name='Maria'
        )
        self.url = reverse('blog:like_toggle', args=[self.post.slug])

    def test_visitor_cannot_like(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)
        self.assertFalse(Like.objects.exists())

    def test_visitor_sees_count_and_login_prompt(self):
        Like.objects.create(post=self.post, user=self.maria)
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(response, '1 curtida')
        self.assertContains(response, reverse('accounts:login'))

    def test_like_and_unlike_toggles(self):
        self.client.force_login(self.maria)

        response = self.client.post(self.url)
        self.assertRedirects(
            response, f'{self.post.get_absolute_url()}#curtir',
            fetch_redirect_response=False,
        )
        self.assertEqual(Like.objects.filter(post=self.post, user=self.maria).count(), 1)

        # Clicar de novo descurte (é um "toggle")
        self.client.post(self.url)
        self.assertFalse(Like.objects.filter(post=self.post, user=self.maria).exists())

    def test_liked_state_and_count_shown_on_page(self):
        self.client.force_login(self.maria)
        self.client.post(self.url)

        page = self.client.get(self.post.get_absolute_url())
        self.assertContains(page, 'is-liked')
        self.assertContains(page, '1 curtida')

    def test_get_is_not_allowed(self):
        self.client.force_login(self.maria)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_cannot_like_draft(self):
        draft = make_post('Rascunho', is_published=False)
        self.client.force_login(self.maria)
        response = self.client.post(reverse('blog:like_toggle', args=[draft.slug]))
        self.assertEqual(response.status_code, 404)

    def test_like_count_is_per_post_not_global(self):
        other_post = make_post('Outro post')
        Like.objects.create(post=self.post, user=self.maria)

        response = self.client.get(other_post.get_absolute_url())
        self.assertContains(response, '0 curtida')

    def test_likes_are_deleted_with_account(self):
        Like.objects.create(post=self.post, user=self.maria)
        self.maria.delete()
        self.assertFalse(Like.objects.exists())

    def test_likes_are_deleted_with_post(self):
        Like.objects.create(post=self.post, user=self.maria)
        self.post.delete()
        self.assertFalse(Like.objects.exists())

    def test_rate_limit(self):
        self.client.force_login(self.maria)
        for _ in range(30):
            self.client.post(self.url)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, 'Muitas tentativas')

    def test_most_liked_section_on_home(self):
        popular = make_post('Post popular')
        make_post('Post sem curtidas')
        joao = User.objects.create_user('joao@email.com', 'joao@email.com', 'x')
        Like.objects.create(post=popular, user=self.maria)
        Like.objects.create(post=popular, user=joao)

        response = self.client.get(reverse('blog:index'))

        self.assertContains(response, 'Mais curtidos')
        self.assertContains(response, 'Post popular')
        # Post sem nenhuma curtida não entra na seção "Mais curtidos"
        content = response.content.decode()
        most_liked_section = content.split('Mais curtidos')[1].split('id="posts"')[0]
        self.assertNotIn('Post sem curtidas', most_liked_section)

    def test_most_liked_section_hidden_without_likes(self):
        response = self.client.get(reverse('blog:index'))
        self.assertNotContains(response, 'Mais curtidos')

    def test_most_liked_hidden_on_search_and_pagination(self):
        for i in range(8):
            make_post(f'Post numerado {i}')
        Like.objects.create(post=self.post, user=self.maria)

        self.assertNotContains(
            self.client.get(reverse('blog:index'), {'q': 'post'}), 'Mais curtidos'
        )
        self.assertNotContains(
            self.client.get(reverse('blog:index'), {'page': 2}), 'Mais curtidos'
        )


class ShareButtonsTests(TestCase):
    def test_share_links_use_absolute_url_and_title(self):
        post = make_post('Compartilhe comigo')
        response = self.client.get(post.get_absolute_url())

        self.assertContains(response, 'https://wa.me/?text=')
        self.assertContains(response, 'https://twitter.com/intent/tweet?text=')
        self.assertContains(
            response, f'http%3A//testserver{post.get_absolute_url()}'
        )
        self.assertContains(response, 'share-copy')
        self.assertContains(response, f'data-url="http://testserver{post.get_absolute_url()}"')

    def test_search_results_keep_relevance_order_with_likes_annotation(self):
        # Garante que o annotate() de curtidas não bagunçou a ordem por
        # relevância da busca (ver correção do UnorderedObjectListWarning).
        docker = make_post('Tudo sobre Docker', content='docker docker docker container')
        pouco = make_post('Um post qualquer', content='fala de docker de leve')
        joao = User.objects.create_user('joao@email.com', 'joao@email.com', 'x')
        # O post menos relevante tem mais curtidas, mas isso não deve mudar
        # a ordem da busca (que é por relevância, não por popularidade).
        Like.objects.create(post=pouco, user=joao)

        response = self.client.get(reverse('blog:index'), {'q': 'docker'})
        content = response.content.decode()
        self.assertLess(content.index(docker.title), content.index(pouco.title))
