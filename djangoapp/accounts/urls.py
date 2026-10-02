from django.urls import path

from accounts import views

app_name = 'accounts'

urlpatterns = [
    path('criar/', views.register, name='register'),
    path('entrar/', views.EmailLoginView.as_view(), name='login'),
    path('sair/', views.AccountLogoutView.as_view(), name='logout'),
]
