from django.contrib.syndication.views import Feed
from django.urls import reverse_lazy

from blog.models import Post
from site_setup.models import SiteSetup


class LatestPostsFeed(Feed):
    # Feed RSS: leitores como Feedly avisam seus seguidores a cada post novo.
    link = reverse_lazy('blog:index')

    def title(self):
        setup = SiteSetup.objects.order_by('id').first()
        return setup.title if setup else 'Blog'

    def description(self):
        setup = SiteSetup.objects.order_by('id').first()
        return setup.description if setup else 'Últimos posts'

    def items(self):
        return Post.objects.published()[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt

    def item_pubdate(self, item):
        return item.published_at
