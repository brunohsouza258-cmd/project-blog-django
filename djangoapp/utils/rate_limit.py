from django.core.cache import cache


def client_ip(request):
    # Usa só o REMOTE_ADDR. Cabeçalhos como X-Forwarded-For podem ser
    # forjados pelo visitante; só confie neles se configurar um proxy
    # (nginx) na frente do Django em produção.
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
