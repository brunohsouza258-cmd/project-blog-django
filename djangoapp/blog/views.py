from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from blog.models import Category, Post
from blog.search import search_posts

POSTS_PER_PAGE = 6


def _paginate(request, posts):
    # get_page() nunca dá erro: ?page=abc ou ?page=999 caem numa página válida.
    return Paginator(posts, POSTS_PER_PAGE).get_page(request.GET.get('page'))


def index(request):
    query = request.GET.get('q', '').strip()[:100]
    posts = search_posts(query) if query else Post.objects.published()
    page_obj = _paginate(request, posts)

    return render(request, 'blog/pages/index.html', {
        'page_obj': page_obj,
        'q': query,
        # O destaque de boas-vindas só aparece na primeira página, sem busca.
        'show_hero': not query and page_obj.number == 1,
    })


def category(request, slug):
    category = get_object_or_404(Category, slug=slug)
    posts = Post.objects.published().filter(category=category)

    return render(request, 'blog/pages/index.html', {
        'page_obj': _paginate(request, posts),
        'category': category,
    })


def post_detail(request, slug):
    # Você (admin) consegue ver rascunhos e posts agendados para conferir
    # antes de publicar. Visitantes só veem os publicados.
    if request.user.is_staff:
        posts = Post.objects.select_related('category')
    else:
        posts = Post.objects.published()

    post = get_object_or_404(posts, slug=slug)

    related = Post.objects.none()
    if post.category:
        related = (
            Post.objects.published()
            .filter(category=post.category)
            .exclude(pk=post.pk)[:3]
        )

    return render(request, 'blog/pages/post.html', {
        'post': post,
        'related': related,
    })
