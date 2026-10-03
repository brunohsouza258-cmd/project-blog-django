from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from blog.forms import CommentForm
from blog.models import Category, Comment, Post
from blog.search import search_posts
from utils.rate_limit import is_rate_limited

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

    comments = post.comments.filter(is_visible=True).select_related('author')

    return render(request, 'blog/pages/post.html', {
        'post': post,
        'related': related,
        'comments': comments,
        'comment_form': CommentForm(),
    })


@login_required
@require_POST
def comment_create(request, slug):
    # Só dá para comentar em post publicado (nunca em rascunho/agendado).
    post = get_object_or_404(Post.objects.published(), slug=slug)
    form = CommentForm(request.POST)

    # Até 10 comentários a cada 10 minutos por pessoa: freia spam.
    if is_rate_limited(request, f'comment:{request.user.pk}', 10, 60 * 10):
        messages.error(request, 'Muitos comentários seguidos. Espere alguns minutos.')
    elif form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        comment.save()
        messages.success(request, 'Comentário publicado.')
    else:
        messages.error(request, form.errors['text'][0])

    return redirect(f'{post.get_absolute_url()}#comentarios')


@login_required
@require_POST
def comment_delete(request, pk):
    comment = get_object_or_404(Comment.objects.select_related('post'), pk=pk)

    # Cada um apaga só o próprio comentário; o admin pode apagar qualquer um.
    if comment.author_id != request.user.pk and not request.user.is_staff:
        messages.error(request, 'Você só pode apagar os seus comentários.')
    else:
        comment.delete()
        messages.info(request, 'Comentário apagado.')

    return redirect(f'{comment.post.get_absolute_url()}#comentarios')
