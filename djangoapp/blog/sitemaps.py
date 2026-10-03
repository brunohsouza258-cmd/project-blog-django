from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from blog.models import Category, Post


class PostSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        # Só posts publicados: rascunhos e agendados nunca entram no mapa.
        return Post.objects.published()

    def lastmod(self, post):
        return post.updated_at


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.5

    def items(self):
        # Só categorias que têm pelo menos um post publicado.
        published = Post.objects.published().values('category')
        return Category.objects.filter(pk__in=published)


class StaticSitemap(Sitemap):
    changefreq = 'daily'
    priority = 1.0

    def items(self):
        return ['blog:index', 'feedback:feedback']

    def location(self, name):
        return reverse(name)


SITEMAPS = {
    'posts': PostSitemap,
    'categorias': CategorySitemap,
    'paginas': StaticSitemap,
}
