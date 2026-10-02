"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

from utils.rate_limit import rate_limit_post

# O login do admin é do próprio Django, então o limite de tentativas é
# aplicado "por fora": no máximo 5 tentativas a cada 15 minutos por IP.
admin.site.login = rate_limit_post('admin-login', 5, 60 * 15)(admin.site.login)

urlpatterns = [
    path('', include('blog.urls')),
    path('conta/', include('accounts.urls')),
    path('feedback/', include('feedback.urls')),
    path('chat/', include('chatbot.urls')),
    # Endereço do admin vem do .env (ADMIN_URL). Um endereço secreto evita
    # que robôs fiquem testando senhas em /admin/.
    path(settings.ADMIN_URL, admin.site.urls),
    # Arquivos enviados pelo admin (favicon, capas dos posts). O serve() do
    # Django bloqueia caminhos como "../" e é suficiente para um blog
    # pequeno; com muito acesso, deixe o nginx servir a pasta media.
    re_path(
        r'^media/(?P<path>.*)$', serve,
        {'document_root': settings.MEDIA_ROOT},
    ),
]
