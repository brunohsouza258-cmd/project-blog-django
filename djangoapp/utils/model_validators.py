from django.core.exceptions import ValidationError


# Validador usado em validators=[validate_png] no ImageField. O Django chama
# essa função no formulário (ex.: no admin) antes de salvar; se ela levantar
# ValidationError, a mensagem aparece embaixo do campo e nada é salvo.
# Obs.: confere só a extensão do nome, não o conteúdo real do arquivo.
def validate_png(image):
    if not image.name.lower().endswith('.png'):
        raise ValidationError('Imagem precisa ser PNG')
