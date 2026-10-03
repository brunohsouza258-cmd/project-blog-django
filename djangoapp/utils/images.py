from pathlib import Path

from django.conf import settings
from PIL import Image


def resize_image(image_django, new_width=800, optimize=True, quality=60,
                 max_height=None):
    # O ImageField guarda só o caminho relativo (ex.: "assets/favicon/...").
    # Juntando com MEDIA_ROOT temos o caminho real do arquivo no disco.
    image_path = Path(settings.MEDIA_ROOT / image_django.name).resolve()

    # O "with" fecha o arquivo automaticamente ao sair do bloco, mesmo que
    # aconteça algum erro no meio do caminho.
    with Image.open(image_path) as image_pillow:
        original_width, original_height = image_pillow.size

        # Nunca aumenta a imagem: ampliar só deixa ela borrada.
        too_tall = max_height and original_height > max_height
        if original_width <= new_width and not too_tall:
            return image_pillow

        # Regra de três para manter a proporção (não achatar a imagem).
        new_height = round(new_width * original_height / original_width)

        # Fotos em pé (retratos) também são limitadas na altura, senão uma
        # imagem de 1200x1800 continuaria pesada.
        if max_height and new_height > max_height:
            new_height = max_height
            new_width = round(max_height * original_width / original_height)

        # LANCZOS é o filtro de redimensionamento de melhor qualidade do Pillow.
        new_image = image_pillow.resize(
            (new_width, new_height), Image.Resampling.LANCZOS
        )

    # Sobrescreve o arquivo original com a versão menor. "quality" só tem
    # efeito em JPEG; em PNG quem reduz o tamanho é o "optimize".
    new_image.save(
        image_path,
        optimize=optimize,
        quality=quality,
    )

    return new_image
