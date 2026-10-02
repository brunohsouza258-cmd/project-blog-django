from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


def client_ip(request):
    """
    IP de quem fez a requisição.

    Sem proxy (NUM_PROXIES=0), usa o REMOTE_ADDR. Com o site atrás de um
    proxy como o nginx, o REMOTE_ADDR é o IP do proxy e o IP real vem no
    cabeçalho X-Forwarded-For. Esse cabeçalho pode ser forjado pelo
    visitante, então só lemos a posição que o NOSSO proxy escreveu: a
    N-ésima a partir do fim, onde N é o número de proxies.
    """
    num_proxies = settings.NUM_PROXIES

    if num_proxies > 0:
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        ips = [ip.strip() for ip in forwarded.split(',') if ip.strip()]
        if len(ips) >= num_proxies:
            return ips[-num_proxies]

    return request.META.get('REMOTE_ADDR', 'unknown')


def is_rate_limited(request, scope, limit, window):
    """
    Conta quantas vezes este IP fez a ação "scope" na janela de tempo
    (em segundos) e devolve True quando passar de "limit".

    Ex.: is_rate_limited(request, 'login', 10, 600) -> no máximo 10
    tentativas de login a cada 10 minutos por IP.
    """
    key = f'rate:{scope}:{client_ip(request)}'
    # add() só cria a chave se ela não existir: começa a janela de tempo.
    cache.add(key, 0, window)
    try:
        count = cache.incr(key)
    except ValueError:
        # A chave expirou entre o add() e o incr().
        cache.set(key, 1, window)
        count = 1
    return count > limit


def rate_limit_post(scope, limit, window):
    """
    Decorator para views de terceiros (ex.: login do admin) em que não dá
    para editar o código: limita os POSTs por IP e responde 429.
    """
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method == 'POST' and is_rate_limited(
                request, scope, limit, window
            ):
                return HttpResponse(
                    'Muitas tentativas seguidas. Espere alguns minutos.',
                    content_type='text/plain; charset=utf-8',
                    status=429,
                )
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
