from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render

from feedback.forms import FeedbackForm
from utils.rate_limit import is_rate_limited


def feedback(request):
    initial = {}

    # Se a pessoa estiver logada, já preenche nome e e-mail para ela.
    if request.user.is_authenticated:
        initial = {
            'name': request.user.first_name,
            'email': request.user.email,
        }

    form = FeedbackForm(request.POST or None, initial=initial)

    # Até 5 feedbacks a cada 10 minutos por IP (anti-spam).
    if request.method == 'POST' and is_rate_limited(
        request, 'feedback', limit=5, window=60 * 10
    ):
        form.add_error(None, 'Muitos envios seguidos. Espere alguns minutos.')
        return render(
            request, 'feedback/feedback.html', {'form': form}, status=429
        )

    if request.method == 'POST' and form.is_valid():
        # Robô caiu na armadilha: finge que deu certo, mas não salva nada.
        if form.is_spam():
            messages.success(request, 'Obrigado! Seu feedback foi enviado.')
            return redirect('feedback:feedback')

        item = form.save()

        # O feedback já está salvo no banco (aparece no admin). O e-mail é
        # um aviso extra: fail_silently=True evita que um problema no
        # servidor de e-mail mostre erro para o visitante.
        send_mail(
            subject=f'[Blog] Novo feedback de {item.name}',
            message=(
                f'Nome: {item.name}\n'
                f'E-mail: {item.email}\n\n'
                f'{item.message}'
            ),
            from_email=None,  # usa o DEFAULT_FROM_EMAIL do settings.py
            recipient_list=[settings.FEEDBACK_EMAIL],
            fail_silently=True,
        )

        messages.success(request, 'Obrigado! Seu feedback foi enviado.')
        return redirect('feedback:feedback')

    return render(request, 'feedback/feedback.html', {'form': form})
