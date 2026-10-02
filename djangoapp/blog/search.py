import re

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Q

from blog.models import Post

# Peso de cada campo na busca: achar a palavra no título vale mais do que
# achar no meio do texto.
POST_VECTOR = (
    SearchVector('title', weight='A', config='portuguese')
    + SearchVector('excerpt', weight='B', config='portuguese')
    + SearchVector('content', weight='C', config='portuguese')
)


def search_posts(text, queryset=None):
    """
    Busca posts publicados relacionados ao texto, do mais relevante para o
    menos relevante. Usada na busca do site e pela IA do chat.

    Usa a busca textual do PostgreSQL em português: entende variações das
    palavras ("programar" acha "programação") e ignora palavras comuns
    ("de", "como", "sobre").
    """
    if queryset is None:
        queryset = Post.objects.published()

    text = text.strip()[:200]
    # Palavras com 3+ letras, no máximo 10 (evita consultas gigantes).
    words = [w for w in re.findall(r'\w+', text.lower()) if len(w) >= 3][:10]

    if not words:
        return queryset.none()

    # Qualquer palavra conta (OU): "posts sobre docker" acha posts de docker
    # mesmo sem a palavra "posts".
    query = SearchQuery(words[0], config='portuguese')
    for word in words[1:]:
        query |= SearchQuery(word, config='portuguese')

    return (
        queryset
        .annotate(rank=SearchRank(POST_VECTOR, query))
        # O icontains no título cobre nomes próprios e palavras que a busca
        # em português não reconhece.
        .filter(Q(rank__gt=0) | Q(title__icontains=text))
        .order_by('-rank', '-published_at')
    )
