import json
import urllib.error
import urllib.request

from django.conf import settings
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST

from chatbot.context import build_system_prompt
from utils.rate_limit import is_rate_limited

MAX_MESSAGE_LENGTH = 500
MAX_HISTORY = 8
# Limite por visitante: no máximo 20 perguntas a cada 10 minutos. Protege
# o seu PC de alguém mandando mensagens sem parar.
RATE_LIMIT = 20
RATE_WINDOW = 60 * 10

OFFLINE_MESSAGE = (
    'Desculpe, o assistente está indisponível agora. '
    'Tente de novo em instantes ou use a página de feedback.'
)


def _clean_history(raw_history):
    """
    O histórico vem do navegador, então não dá para confiar nele: só aceita
    papéis "user"/"assistant" (nunca "system") e corta textos grandes.
    """
    if not isinstance(raw_history, list):
        return []

    history = []
    for item in raw_history[-MAX_HISTORY:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        content = item.get('content')
        if role in ('user', 'assistant') and isinstance(content, str):
            history.append({'role': role, 'content': content[:1000]})
    return history


def _stream_from_ollama(messages):
    """
    Gerador: pede a resposta ao Ollama em modo "stream" e devolve cada
    pedaço de texto assim que ele chega. O navegador vai mostrando as
    palavras aos poucos, em vez de esperar a resposta inteira.
    """
    payload = json.dumps({
        'model': settings.OLLAMA_MODEL,
        'messages': messages,
        'stream': True,
        'options': {
            # Mais baixo = respostas mais fiéis às informações do blog.
            'temperature': 0.3,
            # Limite de tamanho da resposta (em tokens, ~ pedaços de palavra).
            'num_predict': 300,
        },
    }).encode()

    ollama_request = urllib.request.Request(
        f'{settings.OLLAMA_URL}/api/chat',
        data=payload,
        headers={'Content-Type': 'application/json'},
    )

    try:
        with urllib.request.urlopen(ollama_request, timeout=180) as response:
            # O Ollama manda uma linha JSON por pedaço da resposta.
            for line in response:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                text = chunk.get('message', {}).get('content', '')
                if text:
                    yield text
                if chunk.get('done'):
                    break
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        yield OFFLINE_MESSAGE


@require_POST
def chat(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'JSON inválido.'}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({'error': 'JSON inválido.'}, status=400)

    message = str(data.get('message', '')).strip()

    if not message:
        return JsonResponse({'error': 'Escreva uma pergunta.'}, status=400)

    if len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse(
            {'error': f'Use no máximo {MAX_MESSAGE_LENGTH} caracteres.'},
            status=400,
        )

    if is_rate_limited(request, 'chat', RATE_LIMIT, RATE_WINDOW):
        return HttpResponse(
            'Você enviou muitas perguntas seguidas. '
            'Espere alguns minutos e tente de novo.',
            content_type='text/plain; charset=utf-8',
            status=429,
        )

    messages = [
        {'role': 'system', 'content': build_system_prompt(request)},
        *_clean_history(data.get('history')),
        {'role': 'user', 'content': message},
    ]

    response = StreamingHttpResponse(
        _stream_from_ollama(messages),
        content_type='text/plain; charset=utf-8',
    )
    # Impede proxies (ex.: nginx no futuro) de segurar o stream.
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache'
    return response
