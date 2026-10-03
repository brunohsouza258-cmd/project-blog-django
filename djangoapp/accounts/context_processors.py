def display_name(request):
    """
    Primeiro nome de quem está logado, para o header e as saudações.
    "Maria Clara Souza" vira "Maria". Sem nome, usa o começo do e-mail.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}

    words = user.first_name.split()
    name = words[0] if words else user.email.split('@')[0]

    # Foto de perfil (ou None, e aí o site mostra a inicial do nome)
    # Quem nunca enviou foto ainda não tem perfil: getattr devolve None.
    profile = getattr(user, 'profile', None)
    avatar_url = profile.avatar_url if profile else ''

    return {'display_name': name, 'user_avatar_url': avatar_url}
