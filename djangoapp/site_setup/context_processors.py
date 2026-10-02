from site_setup.models import SiteSetup


# Context processor: roda em TODA requisição que renderiza um template e
# injeta 'site_setup' no contexto. Assim qualquer template (header, footer,
# head...) acessa {{ site_setup.title }} sem cada view precisar enviar isso.
# Está registrado em TEMPLATES > OPTIONS > context_processors no settings.py.
def site_setup(request):
    # first() devolve None quando não há Setup cadastrado, em vez de dar erro.
    setup = SiteSetup.objects.order_by('id').first()
    return {
        'site_setup': setup,
    }
